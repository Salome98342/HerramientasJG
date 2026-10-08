import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
export default defineConfig(function (_a) {
    var _b;
    var mode = _a.mode;
    var env = loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), '');
    return {
        plugins: [react()],
        resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
        server: {
            proxy: {
                '/api': {
                    target: (_b = env.VITE_PROXY_TARGET) !== null && _b !== void 0 ? _b : 'http://localhost:8000',
                    changeOrigin: true,
                    secure: false,
                    cookieDomainRewrite: { '*': '' },
                },
            },
        },
    };
});
