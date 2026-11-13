/** Fit reference previews below hosted request limits; dataset bytes are untouched. */
export async function hostedReferences(files:File[]):Promise<File[]>{
 return Promise.all(files.map(async(file,index)=>{
  if(file.size>10*1024*1024)throw new Error("Reference images must be no larger than 10 MB each.");
  let image:ImageBitmap;try{image=await createImageBitmap(file)}catch{throw new Error("This image format cannot be resized for hosted upload. Choose PNG, JPEG or WebP.")}
  try{
   const scale=Math.min(1,1024/Math.max(image.width,image.height));const canvas=document.createElement("canvas");canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));
   const context=canvas.getContext("2d");if(!context)throw new Error("Image processing is unavailable.");context.fillStyle="#fff";context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0,canvas.width,canvas.height);
   for(const quality of [.82,.65,.45,.25]){
    const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,"image/jpeg",quality));
    if(blob&&blob.size<=450*1024)return new File([blob],index+".jpg",{type:"image/jpeg"});
   }
   throw new Error("Reference preview is too large. Choose a smaller image.");
  }finally{image.close()}
 }));
}
