import {build} from 'esbuild';
import {mkdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
await mkdir('static/assets', {recursive:true});
await build({entryPoints:['frontend/main.jsx'], bundle:true, minify:true, outfile:'static/assets/app.js', sourcemap:false, define:{'process.env.NODE_ENV':'"production"'}, loader:{'.js':'jsx'}});
execFileSync(process.execPath, ['node_modules/tailwindcss/lib/cli.js','-i','static/style.src.css','-o','static/assets/style.css','--minify'], {stdio:'inherit'});
