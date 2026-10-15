import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, extname, sep } from 'node:path';
import { spawn } from 'node:child_process';
const root = dirname(fileURLToPath(import.meta.url));
const mime = {'.html':'text/html; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2','.glb':'model/gltf-binary','.bin':'application/octet-stream'};
const server = http.createServer(async (req,res) => {
  if (!['GET','HEAD'].includes(req.method)) {res.writeHead(405); res.end(); return;}
  try {
    const url = new URL(req.url,'http://localhost');
    if (url.pathname === '/health') {res.writeHead(200,{'Content-Type':'application/json'}); res.end('{"app":"WildfireGuardian Showcase","version":1}');return;}
    const rel = decodeURIComponent(url.pathname);
    const file = resolve(root,'.'+(rel==='/'?'/index.html':rel));
    if (!file.startsWith(root+sep) || rel.split('/').some(p=>p.startsWith('.')&&p!=='')) {res.writeHead(403);res.end();return;}
    const info=await stat(file);if(!info.isFile())throw new Error('Not a file');
    res.writeHead(200,{'Content-Type':mime[extname(file)]||'application/octet-stream','Content-Length':info.size,'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"});
    res.end(req.method==='HEAD'?undefined:await readFile(file));
  } catch {res.writeHead(404,{'Content-Type':'text/plain'});res.end('Not found');}
});
const requested = Number(process.env.PORT || 4173);
let retries=0;
server.on('error',e=>{if(e.code==='EADDRINUSE'&&retries<10){retries++;server.listen(requested+retries,'127.0.0.1');}else{console.error(e.message);process.exitCode=1;}});
server.listen(requested,'127.0.0.1',()=>{
 const url=`http://127.0.0.1:${server.address().port}`;console.log(`WildfireGuardian Showcase · ${url}\nLocal exhibition. Press Ctrl+C to stop.`);
 if(process.argv.includes('--open'))spawn(process.platform==='darwin'?'open':process.platform==='win32'?'explorer':'xdg-open',[url],{stdio:'ignore'}).on('error',()=>{});
});
for(const sig of ['SIGINT','SIGTERM'])process.on(sig,()=>server.close(()=>process.exit(0)));
