const CACHE_NAME = 'cloudvault-cache-v1';
const DYNAMIC_CACHE_NAME = 'cloudvault-dynamic-v1';

// Assets to cache immediately on install
const STATIC_ASSETS = [
    '/offline.html',
    '/manifest.json',
    '/static/icons/icon-192x192.svg',
    '/static/icons/icon-512x512.svg'
];

// Install event: cache static assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
});

// Handle messages from the client (e.g. for skipWaiting)
self.addEventListener('message', event => {
    if (event.data && event.data.action === 'skipWaiting') {
        self.skipWaiting();
    }
});

// Activate event: clean up old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.map(key => {
                    if (key !== CACHE_NAME && key !== DYNAMIC_CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event: Network-first for dynamic, Cache-first for static, fallback to offline.html
self.addEventListener('fetch', event => {
    const req = event.request;
    const url = new URL(req.url);

    // Skip non-GET requests (POST, PUT, DELETE should not be cached)
    if (req.method !== 'GET') {
        // Here we could implement background sync queuing using IndexedDB for offline POSTs
        return; 
    }

    // Skip API calls completely for security
    if (url.pathname.startsWith('/api/')) {
        return;
    }

    // Static Assets Strategy (Cache First, fallback to Network)
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(req).then(cachedRes => {
                return cachedRes || fetch(req).then(fetchRes => {
                    return caches.open(CACHE_NAME).then(cache => {
                        cache.put(req, fetchRes.clone());
                        return fetchRes;
                    });
                });
            })
        );
        return;
    }

    // Dynamic Content Strategy (Network First, fallback to Cache, fallback to Offline page)
    event.respondWith(
        fetch(req)
            .then(fetchRes => {
                return caches.open(DYNAMIC_CACHE_NAME).then(cache => {
                    // Cache HTML pages for offline viewing
                    if (req.headers.get('accept').includes('text/html')) {
                        cache.put(req, fetchRes.clone());
                    }
                    return fetchRes;
                });
            })
            .catch(() => {
                // Network failed, check cache
                return caches.match(req).then(cachedRes => {
                    if (cachedRes) {
                        return cachedRes;
                    }
                    // If HTML request and not in cache, show offline page
                    if (req.headers.get('accept').includes('text/html')) {
                        return caches.match('/offline.html');
                    }
                });
            })
    );
});

// Background Sync (Requires modern browser support)
self.addEventListener('sync', event => {
    if (event.tag === 'sync-uploads') {
        event.waitUntil(syncUploads());
    }
});

async function syncUploads() {
    // In a full implementation, you would retrieve queued actions from IndexedDB 
    // and execute them here.
    console.log('[Service Worker] Background sync triggered');
}
