/**
 * GoodQ4All UI - Main Application Logic
 * Handles API communication and UI updates
 */

const API_BASE = 'http://localhost:8000/api';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    // Load system status
    await loadSystemStatus();
    
    // Load videos list
    await loadVideos();
    
    // Setup search
    setupSearch();
}

// Search functionality
function setupSearch() {
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('search-input');
    
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch();
        }
    });
}

async function performSearch() {
    const query = document.getElementById('search-input').value.trim();
    
    if (!query) {
        return;
    }
    
    // Get selected modalities
    const modalities = [];
    if (document.getElementById('text-filter').checked) modalities.push('text');
    if (document.getElementById('visual-filter').checked) modalities.push('visual');
    if (document.getElementById('audio-filter').checked) modalities.push('audio');
    
    // Show loading
    const resultsContainer = document.getElementById('search-results');
    resultsContainer.innerHTML = '<p class="text-center py-8 text-gray-500">Searching...</p>';
    
    try {
        const response = await fetch(`${API_BASE}/search/multimodal`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                top_k: 10,
                modalities: modalities.length > 0 ? modalities : null
            })
        });
        
        if (!response.ok) {
            throw new Error(`Search failed: ${response.statusText}`);
        }
        
        const data = await response.json();
        displaySearchResults(data);
        
    } catch (error) {
        console.error('Search error:', error);
        resultsContainer.innerHTML = `<p class="text-red-500 text-center py-8">Search failed: ${error.message}</p>`;
    }
}

function displaySearchResults(data) {
    const resultsContainer = document.getElementById('search-results');
    
    if (!data.results || data.results.length === 0) {
        resultsContainer.innerHTML = '<p class="text-center py-8 text-gray-500">No results found</p>';
        return;
    }
    
    let html = `<div class="mb-4 text-sm text-gray-600">Found ${data.total_results} results across ${data.modalities_searched.join(', ')}</div>`;
    html += '<div class="space-y-4">';
    
    data.results.forEach((result, idx) => {
        const modalityIcon = result.modality === 'text' ? '📝' : result.modality === 'visual' ? '🎨' : '🎵';
        const score = (result.score * 100).toFixed(1);
        
        html += `
            <div class="card border border-gray-200 rounded-lg p-4 hover:shadow-lg">
                <div class="flex items-start justify-between mb-2">
                    <div class="flex items-center space-x-2">
                        <span class="text-2xl">${modalityIcon}</span>
                        <span class="text-sm font-medium text-gray-600">${result.modality.toUpperCase()}</span>
                        <span class="text-sm text-gray-400">•</span>
                        <span class="text-sm text-purple-600 font-medium">${score}% match</span>
                    </div>
                </div>
                
                ${result.video_id ? `<div class="text-sm text-gray-600 mb-2">Video: <span class="font-mono">${result.video_id}</span></div>` : ''}
                ${result.scene_id !== null ? `<div class="text-sm text-gray-600 mb-2">Scene #${result.scene_id}</div>` : ''}
                ${result.timestamp ? `<div class="text-sm text-gray-600 mb-2">Time: ${result.timestamp.toFixed(1)}s</div>` : ''}
                
                ${result.transcript ? `<p class="text-gray-800 mb-2">${escapeHtml(result.transcript.substring(0, 200))}${result.transcript.length > 200 ? '...' : ''}</p>` : ''}
                
                ${result.keywords && result.keywords.length > 0 ? `
                    <div class="flex flex-wrap gap-1 mb-2">
                        ${result.keywords.slice(0, 5).map(kw => `<span class="px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded">${escapeHtml(kw)}</span>`).join('')}
                    </div>
                ` : ''}
                
                ${result.objects && result.objects.length > 0 ? `
                    <div class="flex flex-wrap gap-1">
                        ${result.objects.slice(0, 5).map(obj => `<span class="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">${escapeHtml(obj)}</span>`).join('')}
                    </div>
                ` : ''}
                
                ${result.representative_frame ? `
                    <div class="mt-3">
                        <img src="/api/media/video/${result.video_id}/frame/${result.representative_frame}" 
                             alt="Scene frame" 
                             class="rounded-md max-w-full h-auto"
                             onerror="this.style.display='none'" />
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    html += '</div>';
    resultsContainer.innerHTML = html;
}

// System status
async function loadSystemStatus() {
    const statusContainer = document.getElementById('system-status');
    
    try {
        const response = await fetch(`${API_BASE}/system/status`);
        
        if (!response.ok) {
            throw new Error(`Status check failed: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        const statusColor = data.status === 'healthy' ? 'green' : data.status === 'degraded' ? 'yellow' : 'red';
        
        statusContainer.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="text-center">
                    <div class="text-3xl font-bold text-${statusColor}-600">${data.status.toUpperCase()}</div>
                    <div class="text-sm text-gray-600">System Status</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl font-bold">${data.total_videos_processed}</div>
                    <div class="text-sm text-gray-600">Videos Processed</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl font-bold">${data.total_scenes_indexed}</div>
                    <div class="text-sm text-gray-600">Scenes Indexed</div>
                </div>
                <div class="text-center">
                    <div class="text-2xl">${data.goodq_core_available ? '✅' : '❌'} ${data.qdrant_available ? '✅' : '❌'}</div>
                    <div class="text-sm text-gray-600">Core / Qdrant</div>
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Status error:', error);
        statusContainer.innerHTML = `<p class="text-red-500">Failed to load system status: ${error.message}</p>`;
    }
}

// Videos list
async function loadVideos() {
    const videosContainer = document.getElementById('videos-list');
    
    try {
        const response = await fetch(`${API_BASE}/system/videos`);
        
        if (!response.ok) {
            throw new Error(`Videos load failed: ${response.statusText}`);
        }
        
        const videos = await response.json();
        
        if (videos.length === 0) {
            videosContainer.innerHTML = '<p class="text-gray-500 col-span-full text-center py-8">No videos processed yet</p>';
            return;
        }
        
        videosContainer.innerHTML = videos.map(video => `
            <div class="card border border-gray-200 rounded-lg p-4 hover:shadow-lg cursor-pointer" onclick="viewVideo('${video.video_id}')">
                <div class="aspect-video bg-gray-100 rounded-md mb-3 flex items-center justify-center text-gray-400">
                    ${video.thumbnail ? `<img src="/api/media/video/${video.video_id}/frame/${video.thumbnail}" class="w-full h-full object-cover rounded-md" onerror="this.parentElement.innerHTML='🎬'" />` : '🎬'}
                </div>
                <h3 class="font-semibold text-gray-800 mb-1 truncate">${escapeHtml(video.title || video.video_id)}</h3>
                <div class="text-sm text-gray-600">
                    ${video.total_scenes ? `${video.total_scenes} scenes` : 'Processing...'}
                    ${video.duration ? ` • ${formatDuration(video.duration)}` : ''}
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Videos load error:', error);
        videosContainer.innerHTML = `<p class="text-red-500 col-span-full">Failed to load videos: ${error.message}</p>`;
    }
}

function viewVideo(videoId) {
    // TODO: Navigate to video detail view
    console.log('View video:', videoId);
    alert(`Video viewer coming soon! Video ID: ${videoId}`);
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}
