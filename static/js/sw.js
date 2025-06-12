// Service Worker per Vintage & Modern
// Gestione cache avanzata per performance ottimali

const CACHE_NAME = 'vintage-modern-v1.2';
const STATIC_CACHE = 'static-v1.2';
const API_CACHE = 'api-v1.2';

// Risorse da cachare immediatamente
const STATIC_ASSETS = [
    '/',
    '/static/css/styles.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/sweetalert2@11'
];

// API endpoints da cachare
const API_ENDPOINTS = [
    '/api/stats',
    '/api/articoli'
];

// Install event - cache delle risorse statiche
self.addEventListener('install', event => {
    console.log('🔧 Service Worker installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('📦 Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('✅ Static assets cached');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('❌ Error caching static assets:', error);
            })
    );
});

// Activate event - pulizia cache vecchie
self.addEventListener('activate', event => {
    console.log('🚀 Service Worker activating...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== STATIC_CACHE && 
                            cacheName !== API_CACHE && 
                            cacheName !== CACHE_NAME) {
                            console.log('🗑️ Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('✅ Service Worker activated');
                return self.clients.claim();
            })
    );
});

// Fetch event - strategia di caching intelligente
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Strategia per API calls
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }
    
    // Strategia per risorse statiche
    if (request.destination === 'style' || 
        request.destination === 'script' || 
        request.destination === 'font') {
        event.respondWith(handleStaticRequest(request));
        return;
    }
    
    // Strategia per immagini
    if (request.destination === 'image') {
        event.respondWith(handleImageRequest(request));
        return;
    }
    
    // Strategia per pagine HTML
    if (request.destination === 'document') {
        event.respondWith(handleDocumentRequest(request));
        return;
    }
    
    // Default: network first
    event.respondWith(fetch(request));
});

// Gestione richieste API - Network First con fallback cache
async function handleApiRequest(request) {
    const cache = await caches.open(API_CACHE);
    
    try {
        // Prova prima la rete
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            // Salva in cache solo se la risposta è ok
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('📡 Network failed, trying cache for:', request.url);
        
        // Fallback alla cache
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Se non c'è nemmeno in cache, ritorna errore
        throw error;
    }
}

// Gestione risorse statiche - Cache First
async function handleStaticRequest(request) {
    const cache = await caches.open(STATIC_CACHE);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        return cachedResponse;
    }
    
    // Se non in cache, scarica e salva
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.error('❌ Failed to fetch static resource:', request.url);
        throw error;
    }
}

// Gestione immagini - Cache First con placeholder
async function handleImageRequest(request) {
    const cache = await caches.open(CACHE_NAME);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        return cachedResponse;
    }
    
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        // Ritorna placeholder per immagini non trovate
        return new Response(
            '<svg width="300" height="300" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#f8f9fa"/><text x="50%" y="50%" font-family="Arial" font-size="14" fill="#6c757d" text-anchor="middle" dy=".3em">Immagine non disponibile</text></svg>',
            {
                headers: {
                    'Content-Type': 'image/svg+xml',
                    'Cache-Control': 'max-age=86400'
                }
            }
        );
    }
}

// Gestione documenti HTML - Network First
async function handleDocumentRequest(request) {
    try {
        return await fetch(request);
    } catch (error) {
        // Fallback alla cache per offline
        const cache = await caches.open(CACHE_NAME);
        const cachedResponse = await cache.match('/');
        return cachedResponse || new Response('Offline - Connessione non disponibile');
    }
}

// Background sync per operazioni offline
self.addEventListener('sync', event => {
    if (event.tag === 'background-sync') {
        console.log('🔄 Background sync triggered');
        event.waitUntil(doBackgroundSync());
    }
});

async function doBackgroundSync() {
    // Implementa logica di sincronizzazione in background
    console.log('🔄 Performing background sync...');
}

// Notifiche push (per future implementazioni)
self.addEventListener('push', event => {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: '/static/icon-192.png',
            badge: '/static/badge-72.png',
            vibrate: [100, 50, 100],
            data: {
                dateOfArrival: Date.now(),
                primaryKey: data.primaryKey
            }
        };
        
        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

// Click su notifiche
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    event.waitUntil(
        clients.openWindow('/')
    );
});

console.log('🎯 Service Worker loaded for Vintage & Modern'); 