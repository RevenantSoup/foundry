import type { NextConfig } from "next";
const config: NextConfig = {output:"standalone", outputFileTracingRoot:process.cwd()+"/..", serverExternalPackages: [], outputFileTracingExcludes: {"/*": ["**/node_modules/@next/swc*/**", "**/node_modules/typescript/**", "**/node_modules/@playwright/**", "**/node_modules/playwright-core/**", "**/node_modules/eslint*/**", "**/node_modules/@eslint/**"]}, allowedDevOrigins: ["127.0.0.1"], devIndicators: false};
export default config;
