// Summary Console JavaScript Coordinator

// App state
const state = {
  dashboard: null,
  activeEntity: null,
  activeCollection: null,
  collections: [],
  currentPlaylistScenes: []
};

// Toast Notifications
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'error' ? '❌' : '⚡'}</span>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Format time in seconds to mm:ss
function formatTimecode(seconds) {
  if (seconds === null || seconds === undefined) return '00:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Convert frame path/name to a safe media endpoint
function getFrameEndpoint(videoId, representativeFrame) {
  if (!representativeFrame) return '';
  // Extract frame filename (e.g., scene_0000_frame_01.jpg)
  const parts = representativeFrame.split(/[\\/]/);
  const filename = parts[parts.length - 1];
  return `/api/media/video/${encodeURIComponent(videoId)}/frame/${encodeURIComponent(filename)}`;
}

// Initial boot
document.addEventListener('DOMContentLoaded', () => {
  setupTabListeners();
  setupModalListeners();
  bootSummaryConsole();
});

// Setup panel tab buttons
function setupTabListeners() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      // Deactivate all
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.hidden = true);
      
      // Activate selected
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      document.getElementById(targetId).hidden = false;
    });
  });
}

// Setup collection modals
function setupModalListeners() {
  const modal = document.getElementById('save-collection-modal');
  const closeBtn = document.getElementById('modal-close-btn');
  const cancelBtn = document.getElementById('modal-cancel-btn');
  const saveBtn = document.getElementById('save-playlist-btn');
  const form = document.getElementById('save-collection-form');
  
  saveBtn.addEventListener('click', () => {
    if (!state.currentPlaylistScenes.length) {
      showToast('Cannot save empty playlist.', 'error');
      return;
    }
    document.getElementById('save-scenes-count').textContent = state.currentPlaylistScenes.length;
    modal.hidden = false;
  });
  
  const closeModal = () => {
    modal.hidden = true;
    form.reset();
  };
  
  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('col-name-input').value.trim();
    const description = document.getElementById('col-desc-input').value.trim();
    
    // Build request payload
    const payload = {
      name: name,
      description: description,
      collection_type: 'manual_playlist',
      query_params: state.activeEntity ? { entity_id: state.activeEntity.entity_id } : { built_in: true },
      scene_refs: state.currentPlaylistScenes.map(s => ({
        video_id: s.video_id,
        scene_id: s.scene_id,
        start: s.start,
        end: s.end,
        representative_frame: s.representative_frame,
        transcript: s.transcript
      })),
      operator_note: `Created from summary workbench playlist with ${state.currentPlaylistScenes.length} scenes.`
    };
    
    try {
      const resp = await fetch('/api/summary/collections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (!resp.ok) throw new Error('Failed to create collection.');
      
      const data = await resp.json();
      showToast(`Collection "${data.collection.name}" saved successfully!`);
      closeModal();
      loadCustomCollections();
    } catch (err) {
      console.error(err);
      showToast(err.message, 'error');
    }
  });
}

// Load scope metadata and dashboard metrics
async function bootSummaryConsole() {
  const status = document.getElementById('system-status');
  try {
    status.textContent = 'Status: LOADING';
    status.className = 'header-status';
    
    const resp = await fetch('/api/summary/dashboard');
    if (!resp.ok) throw new Error('API server returned error on dashboard.');
    
    state.dashboard = await resp.json();
    
    // Update status
    status.textContent = 'Status: ONLINE';
    status.className = 'header-status';
    
    renderScopeMetadata(state.dashboard.scope_metadata);
    renderLeaderboards(state.dashboard);
    loadCustomCollections();
    setupBuiltInHighlights();
  } catch (err) {
    status.textContent = 'Status: OFFLINE';
    status.className = 'header-status offline';
    showToast(`Dashboard initialization failed: ${err.message}`, 'error');
  }
}

// Render scope info in header
function renderScopeMetadata(meta) {
  const container = document.getElementById('scope-info');
  container.innerHTML = `
    <span>Epoch: <strong class="scope-badge">${meta.epoch}</strong></span>
    <span>Database: <strong>${meta.db_path}</strong></span>
    <span>Videos: <strong>${meta.video_count}</strong></span>
    <span>Scenes: <strong>${meta.scene_count}</strong></span>
  `;
}

// Render leaderboards in left tab sections
function renderLeaderboards(data) {
  // 1. People List
  const peopleContainer = document.getElementById('people-list');
  peopleContainer.innerHTML = '';
  if (!data.people || !data.people.length) {
    peopleContainer.innerHTML = '<div class="empty-state">No people nodes indexed.</div>';
  } else {
    data.people.forEach(p => {
      const el = document.createElement('div');
      el.className = 'entity-item';
      el.setAttribute('data-id', p.entity_id);
      el.innerHTML = `
        <span class="entity-name">${p.name}</span>
        <span class="entity-count">${p.occurrence_count} scenes</span>
      `;
      el.addEventListener('click', () => handleEntitySelect(p, el));
      peopleContainer.appendChild(el);
    });
  }

  // 2. Places List
  const placesContainer = document.getElementById('places-list');
  placesContainer.innerHTML = '';
  if (!data.places || !data.places.length) {
    placesContainer.innerHTML = '<div class="empty-state">No places nodes indexed.</div>';
  } else {
    data.places.forEach(pl => {
      const el = document.createElement('div');
      el.className = 'entity-item';
      el.setAttribute('data-id', pl.entity_id);
      el.innerHTML = `
        <span class="entity-name">${pl.name}</span>
        <span class="entity-count">${pl.occurrence_count} scenes</span>
      `;
      el.addEventListener('click', () => handleEntitySelect(pl, el));
      placesContainer.appendChild(el);
    });
  }

  // 3. Occasions List
  const occasionsContainer = document.getElementById('occasions-list');
  occasionsContainer.innerHTML = '';
  if (!data.occasions || !data.occasions.length) {
    occasionsContainer.innerHTML = '<div class="empty-state">No occasion nodes found.</div>';
  } else {
    data.occasions.forEach(occ => {
      const el = document.createElement('div');
      el.className = 'entity-item';
      el.setAttribute('data-id', occ.entity_id);
      el.innerHTML = `
        <div>
          <div class="entity-name">${occ.name}</div>
          <div class="occasion-meta">${occ.occasion_type} / ${occ.source} (${Math.round(occ.confidence * 100)}% conf)</div>
        </div>
        <span class="entity-count">${occ.occurrence_count} occurrences</span>
      `;
      el.addEventListener('click', () => handleEntitySelect(occ, el));
      occasionsContainer.appendChild(el);
    });
  }

  // 4. Moods Tab (Sentiment distribution & Top emotions)
  const dist = data.sentiment_distribution;
  const total = (dist.POSITIVE || 0) + (dist.NEGATIVE || 0) + (dist.NEUTRAL || 0) || 1;
  const posPct = ((dist.POSITIVE || 0) / total) * 100;
  const neuPct = ((dist.NEUTRAL || 0) / total) * 100;
  const negPct = ((dist.NEGATIVE || 0) / total) * 100;
  
  document.getElementById('sent-pos-bar').style.width = `${posPct}%`;
  document.getElementById('sent-neu-bar').style.width = `${neuPct}%`;
  document.getElementById('sent-neg-bar').style.width = `${negPct}%`;
  
  document.getElementById('sent-pos-val').textContent = `${dist.POSITIVE || 0} (${Math.round(posPct)}%)`;
  document.getElementById('sent-neu-val').textContent = `${dist.NEUTRAL || 0} (${Math.round(neuPct)}%)`;
  document.getElementById('sent-neg-val').textContent = `${dist.NEGATIVE || 0} (${Math.round(negPct)}%)`;

  const emotionsContainer = document.getElementById('emotions-list');
  emotionsContainer.innerHTML = '';
  if (!data.top_emotions || !data.top_emotions.length) {
    emotionsContainer.innerHTML = '<div class="empty-state">No emotional markers found.</div>';
  } else {
    data.top_emotions.forEach(emo => {
      const el = document.createElement('div');
      el.className = 'emotion-entry';
      el.innerHTML = `
        <span class="emotion-label">${emo.emotion}</span>
        <span class="emotion-count-val">${emo.count} scenes</span>
      `;
      emotionsContainer.appendChild(el);
    });
  }
}

// Highlight and select left panel items
function handleEntitySelect(entity, element) {
  // Clear other selections
  document.querySelectorAll('.entity-item').forEach(el => el.classList.remove('selected'));
  document.querySelectorAll('.collection-item').forEach(el => el.classList.remove('selected'));
  
  element.classList.add('selected');
  loadEntityProfile(entity.entity_id);
}

// Fetch and render entity profile details
async function loadEntityProfile(entityId) {
  const viewer = document.getElementById('profile-viewer-content');
  const standby = document.getElementById('no-profile-selected');
  const details = document.getElementById('profile-details-view');
  
  try {
    const resp = await fetch(`/api/summary/entity/${encodeURIComponent(entityId)}`);
    if (!resp.ok) throw new Error('Failed to load entity profile details.');
    
    const profile = await resp.json();
    state.activeEntity = profile;
    state.activeCollection = null;
    
    // Update elements
    document.getElementById('profile-name').textContent = profile.name;
    
    const typeBadge = document.getElementById('profile-type');
    typeBadge.textContent = profile.node_type;
    typeBadge.className = `meta-badge badge-${profile.node_type}`;
    
    document.getElementById('profile-occurrences').textContent = profile.occurrence_count;
    
    const spanLabel = document.getElementById('profile-span-label');
    if (profile.first_seen !== null && profile.last_seen !== null) {
      spanLabel.hidden = false;
      document.getElementById('profile-span').textContent = `${formatTimecode(profile.first_seen)} - ${formatTimecode(profile.last_seen)}`;
    } else {
      spanLabel.hidden = true;
    }
    
    // Co-occurrences tag cloud
    const tagCloud = document.getElementById('profile-tag-cloud');
    tagCloud.innerHTML = '';
    if (!profile.co_occurrences || !profile.co_occurrences.length) {
      tagCloud.innerHTML = '<span class="empty-state">No co-occurring entities.</span>';
    } else {
      profile.co_occurrences.forEach(co => {
        const tag = document.createElement('span');
        tag.className = 'cloud-tag';
        tag.textContent = `${co.name} (${co.co_occurrence_count})`;
        tag.addEventListener('click', () => {
          // Select co-occurring node
          const sidebarEl = document.querySelector(`.entity-item[data-id="${co.entity_id}"]`);
          if (sidebarEl) {
            // Auto switch list tab
            const tabBtn = document.querySelector(`.tab-btn[data-tab="${co.node_type}s-list-container"]`);
            if (tabBtn) tabBtn.click();
            handleEntitySelect(co, sidebarEl);
            sidebarEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          } else {
            loadEntityProfile(co.entity_id);
          }
        });
        tagCloud.appendChild(tag);
      });
    }
    
    // Update scenes timeline playlist
    state.currentPlaylistScenes = profile.scenes || [];
    renderPlaylistGrid(profile.scenes);
    
    // Show details
    standby.hidden = true;
    details.hidden = false;
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Render playlist scene cards
function renderPlaylistGrid(scenes) {
  const grid = document.getElementById('playlist-grid');
  grid.innerHTML = '';
  
  if (!scenes || !scenes.length) {
    grid.innerHTML = '<div class="empty-state">No scenes feature this entity in current epoch.</div>';
    return;
  }
  
  scenes.forEach(scene => {
    const card = document.createElement('div');
    card.className = 'scene-card';
    
    const frameUrl = getFrameEndpoint(scene.video_id, scene.representative_frame);
    const hasFrame = !!frameUrl;
    
    card.innerHTML = `
      <div class="scene-card-frame">
        ${hasFrame ? `<img src="${frameUrl}" alt="Scene frame" />` : '<div class="empty-state">NO VISUAL EVIDENCE</div>'}
        <span class="card-video-title">${scene.video_title || scene.video_id}</span>
        <span class="card-timecode">${formatTimecode(scene.start)} - ${formatTimecode(scene.end)}</span>
      </div>
      <div class="scene-card-info">
        <div class="scene-card-id">SCENE ID: ${scene.scene_id.substring(0, 12)}...</div>
        <p class="scene-card-transcript">"${scene.transcript || 'No dialogue transcript recorded.'}"</p>
      </div>
    `;
    grid.appendChild(card);
  });
}

// Predefined highlights listeners
function setupBuiltInHighlights() {
  const items = document.querySelectorAll('#built-in-highlights-list .collection-item');
  items.forEach(el => {
    el.addEventListener('click', () => {
      // Clear other selections
      document.querySelectorAll('.entity-item').forEach(e => e.classList.remove('selected'));
      document.querySelectorAll('.collection-item').forEach(e => e.classList.remove('selected'));
      
      el.classList.add('selected');
      
      const type = el.getAttribute('data-highlight');
      let name = '';
      let list = [];
      
      if (type === 'positive') {
        name = 'All Positive Moments';
        list = state.dashboard.built_in_highlights.positive_moments;
      } else if (type === 'negative') {
        name = 'All Negative Moments';
        list = state.dashboard.built_in_highlights.negative_moments;
      } else {
        name = 'Multi-Person Gatherings';
        list = state.dashboard.built_in_highlights.multi_person_gatherings;
      }
      
      loadBuiltInHighlight(name, list);
    });
  });
}

function loadBuiltInHighlight(name, list) {
  const standby = document.getElementById('no-profile-selected');
  const details = document.getElementById('profile-details-view');
  
  state.activeEntity = null;
  state.activeCollection = null;
  state.currentPlaylistScenes = list;
  
  document.getElementById('profile-name').textContent = name;
  document.getElementById('profile-type').textContent = 'SYSTEM';
  document.getElementById('profile-type').className = 'meta-badge';
  document.getElementById('profile-occurrences').textContent = list.length;
  document.getElementById('profile-span-label').hidden = true;
  document.getElementById('profile-tag-cloud').innerHTML = '<span class="empty-state">System pre-compiled highlight timeline. No co-occurrences graph available.</span>';
  
  renderPlaylistGrid(list);
  
  standby.hidden = true;
  details.hidden = false;
}

// Fetch and render custom collections list
async function loadCustomCollections() {
  const container = document.getElementById('custom-collections-list');
  container.innerHTML = '';
  
  try {
    const resp = await fetch('/api/summary/collections');
    if (!resp.ok) throw new Error('Failed to load custom collections.');
    
    state.collections = await resp.json();
    
    if (!state.collections || !state.collections.length) {
      container.innerHTML = '<div class="empty-state">No custom collections saved.</div>';
      return;
    }
    
    state.collections.forEach(col => {
      const el = document.createElement('div');
      el.className = 'custom-col-item collection-item';
      el.setAttribute('data-id', col.collection_id);
      
      const created = new Date(col.created_at_utc).toLocaleString();
      
      el.innerHTML = `
        <div class="custom-col-header-row">
          <div class="custom-col-details">
            <span class="custom-col-title">${col.name}</span>
            <div class="col-desc">${col.description || 'No description provided.'}</div>
            <div class="custom-col-meta">Created: ${created} (${col.scene_refs.length} scenes)</div>
          </div>
          <button class="col-delete-btn" title="Soft-delete collection">DELETE</button>
        </div>
      `;
      
      // Select click listener
      el.addEventListener('click', (e) => {
        if (e.target.classList.contains('col-delete-btn')) {
          e.stopPropagation();
          handleDeleteCollection(col.collection_id);
          return;
        }
        
        // Clear other selections
        document.querySelectorAll('.entity-item').forEach(item => item.classList.remove('selected'));
        document.querySelectorAll('.collection-item').forEach(item => item.classList.remove('selected'));
        el.classList.add('selected');
        
        loadCustomCollection(col);
      });
      
      container.appendChild(el);
    });
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function loadCustomCollection(col) {
  const standby = document.getElementById('no-profile-selected');
  const details = document.getElementById('profile-details-view');
  
  state.activeEntity = null;
  state.activeCollection = col;
  state.currentPlaylistScenes = col.scene_refs;
  
  document.getElementById('profile-name').textContent = col.name;
  document.getElementById('profile-type').textContent = 'CUSTOM';
  document.getElementById('profile-type').className = 'meta-badge';
  document.getElementById('profile-occurrences').textContent = col.scene_refs.length;
  document.getElementById('profile-span-label').hidden = true;
  document.getElementById('profile-tag-cloud').innerHTML = `
    <div class="custom-col-meta" style="color: var(--text-dim);">
      <strong>Collection ID:</strong> ${col.collection_id}<br/>
      <strong>Source Epoch:</strong> ${col.source_epoch}<br/>
      <strong>Created By:</strong> ${col.created_by}<br/>
      <strong>Created At:</strong> ${new Date(col.created_at_utc).toLocaleString()}
    </div>
  `;
  
  renderPlaylistGrid(col.scene_refs);
  
  standby.hidden = true;
  details.hidden = false;
}

// Delete custom collection
async function handleDeleteCollection(collectionId) {
  if (!confirm(`Are you sure you want to delete collection ${collectionId}?`)) return;
  
  try {
    const resp = await fetch(`/api/summary/collections/${encodeURIComponent(collectionId)}`, {
      method: 'DELETE'
    });
    
    if (!resp.ok) throw new Error('Failed to delete collection.');
    
    showToast('Collection deleted.');
    
    // Clear display if the deleted collection was open
    if (state.activeCollection && state.activeCollection.collection_id === collectionId) {
      document.getElementById('no-profile-selected').hidden = false;
      document.getElementById('profile-details-view').hidden = true;
      state.activeCollection = null;
      state.currentPlaylistScenes = [];
    }
    
    loadCustomCollections();
  } catch (err) {
    showToast(err.message, 'error');
  }
}
