/**
 * Hermes V2 — Frontend API Configuration
 * ═══════════════════════════════════════════════════════════════
 * Change these values to point to your API server.
 * 
 * Usage:
 *   import { apiConfig } from './js/config.js';
 *   const response = await fetch(apiConfig.answerUrl, { ... });
 */

const API_BASE_URL = window.location.origin;

export const apiConfig = {
    baseUrl: API_BASE_URL,
    
    // Endpoints
    answerEndpoint: '/api/answer',
    healthEndpoint: '/api/health',
    docsEndpoint: '/api/docs',
    
    // Full URLs
    get answerUrl() {
        return `${this.baseUrl}${this.answerEndpoint}`;
    },
    get answerStreamUrl() {
        return `${this.baseUrl}${this.answerEndpoint}/stream`;
    },
    get healthUrl() {
        return `${this.baseUrl}${this.healthEndpoint}`;
    },
    get docsUrl() {
        return `${this.baseUrl}${this.docsEndpoint}`;
    },
    
    // Default request options
    defaultOptions: {
        headers: {
            'Content-Type': 'application/json',
        },
        timeout: 300000, // 5 minutes
    },
};

// Legacy support (non-module scripts)
window.apiConfig = apiConfig;
