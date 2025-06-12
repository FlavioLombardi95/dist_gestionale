// Performance Monitoring e Ottimizzazioni per Vintage & Modern
// Sistema avanzato di monitoraggio e ottimizzazione delle performance

class PerformanceMonitor {
    constructor() {
        this.metrics = new Map();
        this.observers = new Map();
        this.init();
    }

    init() {
        this.setupPerformanceObserver();
        this.setupIntersectionObserver();
        this.setupMutationObserver();
        this.monitorNetworkStatus();
        this.setupCriticalResourceHints();
    }

    // Performance Observer per metriche dettagliate
    setupPerformanceObserver() {
        if ('PerformanceObserver' in window) {
            // Core Web Vitals
            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.recordMetric(entry.name, entry.value, entry.entryType);
                    
                    // Log metriche critiche
                    if (['largest-contentful-paint', 'first-input-delay', 'cumulative-layout-shift'].includes(entry.name)) {
                        console.log(`📊 ${entry.name}:`, Math.round(entry.value), 'ms');
                    }
                }
            });

            try {
                observer.observe({ entryTypes: ['measure', 'navigation', 'largest-contentful-paint'] });
            } catch (e) {
                console.log('Performance Observer not fully supported');
            }
        }
    }

    // Intersection Observer per lazy loading ottimizzato
    setupIntersectionObserver() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        this.loadImageOptimized(img);
                        imageObserver.unobserve(img);
                    }
                });
            }, {
                rootMargin: '50px 0px',
                threshold: 0.1
            });

            this.observers.set('images', imageObserver);
        }
    }

    // Mutation Observer per monitorare cambiamenti DOM
    setupMutationObserver() {
        if ('MutationObserver' in window) {
            const mutationObserver = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    if (mutation.type === 'childList') {
                        // Applica lazy loading alle nuove immagini
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1) { // Element node
                                const images = node.querySelectorAll ? node.querySelectorAll('img[data-src]') : [];
                                images.forEach(img => {
                                    this.observers.get('images')?.observe(img);
                                });
                            }
                        });
                    }
                });
            });

            mutationObserver.observe(document.body, {
                childList: true,
                subtree: true
            });

            this.observers.set('mutations', mutationObserver);
        }
    }

    // Caricamento immagini ottimizzato
    loadImageOptimized(img) {
        const src = img.dataset.src;
        if (!src) return;

        // Preload dell'immagine
        const imageLoader = new Image();
        imageLoader.onload = () => {
            img.src = src;
            img.classList.remove('lazy');
            img.classList.add('loaded');
            
            // Animazione di fade-in
            img.style.opacity = '0';
            img.style.transition = 'opacity 0.3s ease';
            requestAnimationFrame(() => {
                img.style.opacity = '1';
            });
        };
        
        imageLoader.onerror = () => {
            img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjhmOWZhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzZjNzU3ZCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkVycm9yZSBjYXJpY2FtZW50bzwvdGV4dD48L3N2Zz4=';
            img.classList.remove('lazy');
        };
        
        imageLoader.src = src;
    }

    // Monitoraggio stato rete
    monitorNetworkStatus() {
        if ('navigator' in window && 'connection' in navigator) {
            const connection = navigator.connection;
            
            const updateNetworkStatus = () => {
                const networkInfo = {
                    effectiveType: connection.effectiveType,
                    downlink: connection.downlink,
                    rtt: connection.rtt,
                    saveData: connection.saveData
                };
                
                this.recordMetric('network-info', networkInfo, 'network');
                
                // Adatta comportamento in base alla connessione
                if (connection.saveData || connection.effectiveType === 'slow-2g') {
                    this.enableDataSaverMode();
                }
            };

            connection.addEventListener('change', updateNetworkStatus);
            updateNetworkStatus();
        }
    }

    // Modalità risparmio dati
    enableDataSaverMode() {
        console.log('📱 Data Saver Mode attivato');
        
        // Disabilita animazioni non essenziali
        document.documentElement.style.setProperty('--transition', 'none');
        
        // Riduce qualità immagini (se supportato)
        document.querySelectorAll('img[data-src]').forEach(img => {
            const src = img.dataset.src;
            if (src && src.includes('uploads/')) {
                // Aggiungi parametri per immagini più piccole se il backend li supporta
                img.dataset.src = src + '?quality=low';
            }
        });
    }

    // Resource hints per performance
    setupCriticalResourceHints() {
        // Prefetch delle risorse probabilmente necessarie
        this.prefetchResource('/api/stats', 'fetch');
        
        // Preconnect a domini esterni
        this.preconnectDomain('https://cdn.jsdelivr.net');
        this.preconnectDomain('https://cdnjs.cloudflare.com');
    }

    prefetchResource(url, as = 'fetch') {
        const link = document.createElement('link');
        link.rel = 'prefetch';
        link.href = url;
        if (as !== 'fetch') link.as = as;
        document.head.appendChild(link);
    }

    preconnectDomain(domain) {
        const link = document.createElement('link');
        link.rel = 'preconnect';
        link.href = domain;
        link.crossOrigin = 'anonymous';
        document.head.appendChild(link);
    }

    // Registrazione metriche
    recordMetric(name, value, type = 'custom') {
        const timestamp = performance.now();
        const metric = { name, value, type, timestamp };
        
        if (!this.metrics.has(name)) {
            this.metrics.set(name, []);
        }
        
        this.metrics.get(name).push(metric);
        
        // Mantieni solo le ultime 100 metriche per tipo
        const metrics = this.metrics.get(name);
        if (metrics.length > 100) {
            metrics.shift();
        }
    }

    // Ottimizzazione automatica
    optimizePerformance() {
        // Cleanup degli observer non utilizzati
        this.cleanupObservers();
        
        // Garbage collection manuale per cache
        if (window.articoliCache) {
            const now = Date.now();
            for (const [key, value] of window.articoliCache.entries()) {
                if (now - value.timestamp > 300000) { // 5 minuti
                    window.articoliCache.delete(key);
                }
            }
        }
        
        // Ottimizza DOM
        this.optimizeDOM();
    }

    cleanupObservers() {
        // Rimuovi observer per elementi non più presenti
        const images = document.querySelectorAll('img[data-src]');
        if (images.length === 0 && this.observers.has('images')) {
            this.observers.get('images').disconnect();
        }
    }

    optimizeDOM() {
        // Rimuovi elementi nascosti non necessari
        const hiddenElements = document.querySelectorAll('.d-none:not([data-keep])');
        hiddenElements.forEach(el => {
            if (!el.closest('.template')) {
                el.remove();
            }
        });
    }

    // Report delle performance
    getPerformanceReport() {
        const report = {
            timestamp: new Date().toISOString(),
            metrics: Object.fromEntries(this.metrics),
            navigation: performance.getEntriesByType('navigation')[0],
            memory: performance.memory ? {
                used: Math.round(performance.memory.usedJSHeapSize / 1048576),
                total: Math.round(performance.memory.totalJSHeapSize / 1048576),
                limit: Math.round(performance.memory.jsHeapSizeLimit / 1048576)
            } : null
        };
        
        return report;
    }

    // Cleanup
    destroy() {
        this.observers.forEach(observer => observer.disconnect());
        this.observers.clear();
        this.metrics.clear();
    }
}

// Inizializzazione automatica
let performanceMonitor;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        performanceMonitor = new PerformanceMonitor();
        
        // Ottimizzazione periodica
        setInterval(() => {
            performanceMonitor.optimizePerformance();
        }, 60000); // Ogni minuto
    });
} else {
    performanceMonitor = new PerformanceMonitor();
}

// Esporta per uso globale
window.PerformanceMonitor = PerformanceMonitor;
window.performanceMonitor = performanceMonitor;

console.log('🚀 Performance Monitor inizializzato'); 