const CACHE='uganda-dating-v6';
const STATIC_ASSETS=[
  '/static/css/style.css?v=20261006-photos-age-gps',
  '/static/img/icon.svg',
  '/static/images/uganda-dating-hero.jpg?v=20261006-hero',
  '/manifest.webmanifest'
];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(STATIC_ASSETS)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  const u=new URL(e.request.url);
  if(u.origin!==location.origin)return;
  if(u.pathname.startsWith('/static/')){
    e.respondWith(caches.match(e.request).then(cached=>{
      const update=fetch(e.request).then(r=>{if(r.ok)caches.open(CACHE).then(c=>c.put(e.request,r.clone()));return r}).catch(()=>cached);
      return cached||update;
    }));
    return;
  }
  e.respondWith(fetch(e.request));
});