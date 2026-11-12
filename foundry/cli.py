"""Foundry's resumable offline-first command line."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import uuid
import click
import imagehash
from PIL import Image
import requests
import ffmpeg
from .db import Database
from .adapters.openverse import OpenverseAdapter
from .adapters.youtube import YouTubeAdapter
from .quota import QuotaExceeded
from .cascade.embed import Embedder, filter_batch
from .cascade.verify import StubVerifier, OpenAIVerifier
from .qa import create_sheet, read_verdicts
from .package import package_batch

@click.group()
@click.option('--root',type=click.Path(path_type=Path),default='data',show_default=True)
@click.pass_context
def cli(ctx,root):
    """Turn an image specification into a versioned labeled dataset."""
    root=root.resolve(); root.mkdir(parents=True,exist_ok=True)
    db=Database(root/'foundry.sqlite3')
    ctx.obj={'root':root,'db':db}
    ctx.call_on_close(db.close)

def load_batch(obj,batch):
    row=obj['db'].conn.execute('SELECT plan FROM batches WHERE id=?',(batch,)).fetchone()
    if not row:
        raise click.ClickException(f'Unknown batch: {batch}')
    return json.loads(row[0])

@cli.command()
@click.option('--prompt',required=True)
@click.option('--refs',required=True,type=click.Path(exists=True,file_okay=False,path_type=Path))
@click.option('--target',type=click.IntRange(min=200),default=200,show_default=True)
@click.option('--threshold',type=click.FloatRange(min=-1,max=1),default=.28,show_default=True)
@click.option('--live',is_flag=True,help='Use real source APIs and CLIP instead of synthetic fixtures.')
@click.pass_obj
def plan(obj,prompt,refs,target,threshold,live):
    """Write a deterministic planner shape and persist a new batch."""
    if not prompt.strip():
        raise click.ClickException('Prompt must not be blank')
    files=[]
    for path in sorted(refs.iterdir()):
        if path.is_file():
            try:
                with Image.open(path) as im: im.verify()
                files.append(str(path.resolve()))
            except (OSError,ValueError):
                continue
    if len(files)!=6:
        raise click.ClickException('Provide exactly six readable reference images')
    batch=uuid.uuid4().hex
    payload={'batch_id':batch,'prompt':prompt,'refs':files,'target':target,
             'threshold':threshold,'offline':not live,'search_terms':[prompt],
             'hashtags':['#'+''.join(prompt.title().split())],
             'negative_terms':['illustration','watermark'],
             'checklist':[f'The image visibly depicts: {prompt}']}
    destination=obj['root']/'plans'; destination.mkdir(exist_ok=True)
    path=destination/(batch+'.json')
    path.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    with obj['db'].conn:
        obj['db'].conn.execute('INSERT INTO batches(id,plan) VALUES(?,?)',(batch,json.dumps(payload)))
    click.echo(f'batch_id={batch}\n{path}')

@cli.command()
@click.option('--batch',required=True)
@click.option('--video-dir',type=click.Path(exists=True,file_okay=False,path_type=Path))
@click.option('--limit',type=click.IntRange(min=1),help='Per-source result limit (default: 2 × target).')
@click.pass_obj
def harvest(obj,batch,video_dir,limit):
    """Harvest both adapters independently; reruns reuse global URL state."""
    plan=load_batch(obj,batch); db=obj['db']; raw=obj['root']/'raw'; raw.mkdir(exist_ok=True)
    adapters=[OpenverseAdapter(offline=plan['offline']),
              YouTubeAdapter(db,offline=plan['offline'],api_key=os.getenv('YOUTUBE_API_KEY'),video_dir=video_dir)]
    count=0; failures=0
    for adapter in adapters:
        try:
            rows=adapter.search(plan['search_terms'][0],limit or 2*plan['target'])
        except QuotaExceeded:
            raise
        except (requests.RequestException,OSError,ValueError,KeyError,ffmpeg.Error) as error:
            failures+=1
            click.echo(f'{type(adapter).__name__}: {error}',err=True)
            continue
        for row in rows:
            row.batch_id=batch
            if db.conn.execute('SELECT 1 FROM rows WHERE id=?',(row.id,)).fetchone():
                with db.conn:
                    db.conn.execute('INSERT OR IGNORE INTO seen_urls VALUES(?,?)',(row.source_url,row.id))
                    db.drop(row,'existing_id')
                continue
            if db.conn.execute('SELECT 1 FROM seen_urls WHERE url=?',(row.source_url,)).fetchone():
                with db.conn: db.drop(row,'seen_url')
                continue
            try:
                payload=adapter.fetch(row)
                with Image.open(io.BytesIO(payload)) as image:
                    image.load(); row.phash=str(imagehash.phash(image))
                row.licence=adapter.licence(row)
                # Store bytes before committing the row so interrupted inserts never leave a missing file.
                path=raw/row.id; temporary=raw/(row.id+'.tmp')
                temporary.write_bytes(payload); temporary.replace(path)
                if db.insert(row):
                    count+=1
                else:
                    path.unlink(missing_ok=True)
            except QuotaExceeded:
                raise
            except (requests.RequestException,OSError,ValueError,KeyError,ffmpeg.Error) as error:
                with db.conn: db.drop(row,'fetch_or_rights: '+str(error))
                click.echo(f'{row.id}: {error}',err=True)
    if failures==len(adapters):
        raise click.ClickException('All sources failed; retry to resume')
    click.echo(f'Harvested {count}; batch total {len(db.rows(batch))}')

@cli.command(name='filter')
@click.option('--batch',required=True)
@click.option('--verifier',type=click.Choice(['stub','openai']),default='stub',show_default=True)
@click.pass_obj
def filter_command(obj,batch,verifier):
    """Embed everything, retrieve 3 × target, verify only the shortlist."""
    plan=load_batch(obj,batch)
    engine=StubVerifier()
    if verifier=='openai':
        key=os.getenv('OPENAI_API_KEY')
        if not key: raise click.ClickException('OPENAI_API_KEY is required')
        engine=OpenAIVerifier(key)
    try:
        count=filter_batch(obj['db'],batch,plan,obj['root']/'raw',
                           Embedder('stub' if plan['offline'] else 'clip'),engine,obj['root'])
    except (ValueError,OSError,requests.RequestException,ImportError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f'Shortlist: {count}; backend: {"stub (synthetic scores)" if plan["offline"] else "CLIP"}')

@cli.command()
@click.option('--batch',required=True)
@click.option('--verdicts',type=click.Path(exists=True,dir_okay=False,path_type=Path))
@click.option('--stub-verdicts',type=click.Choice(['accept','reject']),help='Explicit synthetic QA for offline demo batches only.')
@click.pass_obj
def qa(obj,batch,verdicts,stub_verdicts):
    """Create 200 crops and contact sheet; ingest explicit review verdicts."""
    plan=load_batch(obj,batch)
    try:
        sheet,template=create_sheet(obj['db'],batch,obj['root']/'raw',obj['root']/'qa'/batch)
        click.echo(f'Contact sheet: {sheet}\nVerdicts: {template}')
        if stub_verdicts:
            if not plan['offline'] or any(not r.source_url.startswith('stub://') for r in obj['db'].rows(batch)):
                raise ValueError('Synthetic QA is allowed only for wholly synthetic offline batches')
            if verdicts: raise ValueError('Choose --verdicts or --stub-verdicts')
            records=list(csv.DictReader(template.open(encoding='utf-8')))
            with template.open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=['id','verdict']); writer.writeheader()
                writer.writerows({'id':r['id'],'verdict':stub_verdicts} for r in records)
            verdicts=template
            click.echo('SYNTHETIC QA: these verdicts are for pipeline testing only')
        if verdicts:
            precision=read_verdicts(obj['db'],batch,verdicts)
            click.echo(f'Precision: {precision:.3f}; QA passed')
        else:
            click.echo('Review all 200 images, fill verdicts.csv with accept/reject, then rerun with --verdicts. Packaging remains blocked.')
    except (ValueError,OSError) as error:
        raise click.ClickException(str(error)) from error

@cli.command(name='package')
@click.option('--batch',required=True)
@click.pass_obj
def package_command(obj,batch):
    """Export a QA-approved content-versioned dataset and manifest.csv."""
    load_batch(obj,batch)
    try:
        path=package_batch(obj['db'],batch,obj['root']/'raw',obj['root']/'packages')
    except (ValueError,OSError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(path)

if __name__=='__main__':
    cli()
