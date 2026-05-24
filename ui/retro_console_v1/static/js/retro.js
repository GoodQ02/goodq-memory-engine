(function () {
  "use strict";

  // App State Model
  const state = {
    videos: [],
    activeVideoId: null,
    scenes: [],
    videoMeta: null,       // Sprint 3: timeline/full metadata rollup
    searchResults: [],
    selectedEntity: null,
    selectedEntities: [],
    searchActive: false,
    selectedSceneId: null,
    modes: new Set(["text", "visual", "audio"]),
    graph: { nodes: [], edges: [] },
    canvasOffset: { x: 0, y: 0 },
    canvasScale: 1.0,
    targetOffset: { x: 0, y: 0 },
    targetScale: 1.0,
    isDragging: false,
    dragStart: { x: 0, y: 0 },
    activeNode: null,
    lastQuery: "",
    intelVisible: false,   // Sprint 3: Intel panel open state
    intelFilter: null,     // Sprint 3+: {type, value} filter from intel panel
    graphMode: "2D",       // "2D" or "3D"
    graphRotation: { alpha: 0.2, beta: 0.15 },
    graphSpinSpeed: { alpha: 0.0025, beta: 0.0008 },
    targetRotation: { alpha: 0.2, beta: 0.15 },
    isSpinning: true,
    isAutoRotating: false,
  };

  // ─── Text-to-Speech (Web Speech API) ──────────────────────────
  const tts = {
    supported: typeof window !== 'undefined' && 'speechSynthesis' in window,
    playing: false,
    activePlayAllBtn: null,
    activeRowBtn: null,
    activeRow: null,
    voice: null,    // active SpeechSynthesisVoice
    voices: [],     // all loaded voices
  };

  // Priority list of preferred voice name substrings (en-GB first)
  const TTS_VOICE_PRIORITY = [
    'Sonia',   // Microsoft Sonia Online (Natural) - en-GB
    'Ryan',    // Microsoft Ryan Online (Natural)  - en-GB
    'Libby',   // Microsoft Libby Online (Natural) - en-GB
    'Mia',     // Microsoft Mia Online (Natural)   - en-GB
    'Google UK English Female',
    'Google UK English Male',
  ];

  // Short display label for a voice (strips vendor prefix and locale suffix)
  function ttsVoiceLabel(v) {
    return v.name
      .replace('Microsoft ', '')
      .replace(/ Online \(Natural\)/i, ' ★')
      .replace(/ - English \(United Kingdom\)/i, '')
      .replace(/ - English \(United States\)/i, ' US')
      .replace(/ - English \(Australia\)/i, ' AU')
      .trim();
  }

  function ttsLoadVoices() {
    if (!tts.supported) return;
    const all = window.speechSynthesis.getVoices();
    if (!all || all.length === 0) return;
    tts.voices = all;

    // If user already made a manual pick, don't override
    if (tts.voice) return;

    // 1. Exact priority name match (any lang)
    for (const hint of TTS_VOICE_PRIORITY) {
      const v = all.find(x => x.name.includes(hint));
      if (v) { tts.voice = v; return; }
    }
    // 2. Any en-GB Natural / Online voice
    const ngb = all.find(x => x.lang === 'en-GB' && /Natural|Online/i.test(x.name));
    if (ngb) { tts.voice = ngb; return; }
    // 3. Any en-GB voice
    const gb = all.find(x => x.lang === 'en-GB');
    if (gb) { tts.voice = gb; return; }
    // 4. Any en-US Natural / Online voice
    const nus = all.find(x => x.lang === 'en-US' && /Natural|Online/i.test(x.name));
    if (nus) { tts.voice = nus; return; }
    // 5. Leave null — browser default
  }

  function initTTS() {
    if (!tts.supported) return;
    // getVoices() may return [] synchronously on first call in some browsers
    ttsLoadVoices();
    window.speechSynthesis.addEventListener('voiceschanged', ttsLoadVoices);
  }

  function ttsStop() {
    if (tts.supported) window.speechSynthesis.cancel();
    tts.playing = false;
    if (tts.activePlayAllBtn) {
      tts.activePlayAllBtn.textContent = '▶ PLAY ALL';
      tts.activePlayAllBtn.classList.remove('tts-active');
      tts.activePlayAllBtn = null;
    }
    if (tts.activeRowBtn) {
      tts.activeRowBtn.textContent = '▶';
      tts.activeRowBtn.classList.remove('tts-active');
      tts.activeRowBtn = null;
    }
    if (tts.activeRow) {
      tts.activeRow.classList.remove('tts-playing');
      tts.activeRow = null;
    }
  }

  function ttsSpeak(text, onEnd) {
    if (!tts.supported) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 0.92;
    utt.pitch = 1.0;
    if (tts.voice) utt.voice = tts.voice;
    utt.onend = onEnd || null;
    utt.onerror = onEnd || null;
    window.speechSynthesis.speak(utt);
  }

  // Play a single transcript row; manages button + row highlight state
  function ttsPlayRow(rowEl, btn, text) {
    const wasSelf = tts.activeRowBtn === btn;
    ttsStop();
    if (wasSelf) return; // second click on same row = stop
    tts.playing = true;
    tts.activeRowBtn = btn;
    tts.activeRow = rowEl;
    btn.textContent = '■';
    btn.classList.add('tts-active');
    rowEl.classList.add('tts-playing');
    ttsSpeak(text, () => {
      if (tts.activeRowBtn === btn) ttsStop();
    });
  }

  // Play all transcript rows sequentially
  function ttsPlayAll(rows, playAllBtn) {
    const wasPlaying = tts.activePlayAllBtn === playAllBtn;
    ttsStop();
    if (wasPlaying) return; // second click = stop
    tts.activePlayAllBtn = playAllBtn;
    tts.playing = true;
    playAllBtn.textContent = '■ STOP';
    playAllBtn.classList.add('tts-active');

    let idx = 0;
    function next() {
      if (!tts.playing || idx >= rows.length) {
        ttsStop();
        return;
      }
      const { rowEl, rowBtn, text } = rows[idx++];
      // Clear previous row highlight
      document.querySelectorAll('.transcript-row.tts-playing').forEach(r => r.classList.remove('tts-playing'));
      if (tts.activeRowBtn) { tts.activeRowBtn.textContent = '▶'; tts.activeRowBtn.classList.remove('tts-active'); }
      tts.activeRow = rowEl;
      tts.activeRowBtn = rowBtn;
      rowEl.classList.add('tts-playing');
      rowEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      if (rowBtn) { rowBtn.textContent = '■'; rowBtn.classList.add('tts-active'); }
      ttsSpeak(text, next);
    }
    next();
  }

  // Helper Utility: Entity Name Normalizer and Alias Resolution
  const entityAliases = {
    "anthony": "tony",
    "tony s.": "tony",
    "speaker 2": "tony",
    "male speaker 2": "tony",
    "man in black jacket": "tony",
    "tony": "tony",
    
    "charles": "charlie",
    "charlie": "charlie",
    
    "joseph": "jose",
    "jose": "jose"
  };

  const canonicalDisplayNames = {
    "tony": "Tony",
    "charlie": "Charlie",
    "jose": "Jose"
  };

  function normalizeEntityName(name) {
    const cleaned = String(name || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
    return entityAliases[cleaned] || cleaned;
  }

  function getCanonicalLabel(id, rawName) {
    if (canonicalDisplayNames[id]) {
      return canonicalDisplayNames[id];
    }
    const label = rawName || id;
    if (label === label.toLowerCase()) {
      return label.replace(/\b\w/g, c => c.toUpperCase());
    }
    return label;
  }

  // DOM Text Insertion Helper
  function appendText(parent, tag, text, className) {
    const el = document.createElement(tag);
    el.textContent = text;
    if (className) {
      el.className = className;
    }
    parent.appendChild(el);
    return el;
  }

  // Format seconds to MM:SS
  function formatTime(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const min = Math.floor(total / 60);
    const sec = total % 60;
    return `${min}:${String(sec).padStart(2, "0")}`;
  }

  // Safe string check
  function safeString(value) {
    if (value === null || value === undefined) return "";
    return String(value);
  }

  // API Call Wrapper: GET
  async function apiGet(path) {
    const response = await fetch(path, { method: "GET" });
    if (!response.ok) {
      throw new Error(`GET ${path} failed: ${response.status}`);
    }
    return response.json();
  }

  // API Call Wrapper: POST
  async function apiPost(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`POST ${path} failed: ${response.status}`);
    }
    return response.json();
  }

  // Normalize any entity list from API (handles string[], {name}[], {label}[] etc.)
  function normalizeEntityList(raw) {
    if (!Array.isArray(raw)) return [];
    return raw.map((item) => {
      if (typeof item === "string") return { name: item, type: "generic" };
      return {
        name: item.label || item.name || item.text || "generic",
        type: item.entity_type || item.type || item.category || "generic",
      };
    }).filter((e) => e.name && e.name !== "generic" || e.name);
  }

  // Channel priority: scene_present > dialogue_mentioned > candidate > generic
  const CHANNEL_PRIORITY = { scene_present: 3, dialogue_mentioned: 2, candidate: 1, generic: 0 };

  // Parse entities and co-occurrences to build nodes & edges (channel-aware)
  function buildEntityGraph(scenes) {
    const nodes = new Map();
    const edges = new Map();

    scenes.forEach((scene) => {
      // ── Collect all entity ids from all channels for this scene ──
      const channelSources = [
        { list: scene.scene_present_entities || [], channel: "scene_present" },
        { list: scene.dialogue_mentioned_entities || [], channel: "dialogue_mentioned" },
        { list: scene.candidate_visible_people || [], channel: "candidate" },
        { list: scene.entities || [], channel: "generic" },
      ];

      const sceneEntityIds = new Set();

      channelSources.forEach(({ list, channel }) => {
        list.forEach((entity) => {
          const rawName = typeof entity === "string" ? entity : (entity.name || "");
          if (!rawName) return;
          const id = normalizeEntityName(rawName);
          if (!id) return;
          sceneEntityIds.add(id);

          const existing = nodes.get(id);
          const rawType = typeof entity === "object" ? (entity.entity_type || entity.type || channel) : channel;

          if (!existing) {
            nodes.set(id, {
              id,
              label: getCanonicalLabel(id, rawName),
              type: rawType,
              channel,
              channelPriority: CHANNEL_PRIORITY[channel] ?? 0,
              count: 1,
              sceneIds: [scene.id],
            });
          } else {
            // Upgrade channel if higher priority
            const incomingPriority = CHANNEL_PRIORITY[channel] ?? 0;
            if (incomingPriority > (existing.channelPriority ?? 0)) {
              existing.channel = channel;
              existing.channelPriority = incomingPriority;
              existing.type = rawType;
            }
            existing.count += 1;
            if (!existing.sceneIds.includes(scene.id)) existing.sceneIds.push(scene.id);
          }
        });
      });

      // ── Build co-occurrence edges across all entities in this scene ──
      const ids = Array.from(sceneEntityIds);
      for (let i = 0; i < ids.length; i += 1) {
        for (let j = i + 1; j < ids.length; j += 1) {
          const a = ids[i];
          const b = ids[j];
          const key = [a, b].sort().join("::");
          const existing = edges.get(key) || { source: a, target: b, weight: 0, sceneIds: [] };
          existing.weight += 1;
          if (!existing.sceneIds.includes(scene.id)) existing.sceneIds.push(scene.id);
          edges.set(key, existing);
        }
      }
    });

    return {
      nodes: Array.from(nodes.values()),
      edges: Array.from(edges.values()),
    };
  }

  // 3D rotation matrix calculation
  function rotate3d(x, y, z, alpha, beta) {
    // Rotate around Y-axis (yaw)
    const cosA = Math.cos(alpha);
    const sinA = Math.sin(alpha);
    const x1 = x * cosA - z * sinA;
    const z1 = x * sinA + z * cosA;

    // Rotate around X-axis (pitch)
    const cosB = Math.cos(beta);
    const sinB = Math.sin(beta);
    const y2 = y * cosB - z1 * sinB;
    const z2 = y * sinB + z1 * cosB;

    return { x: x1, y: y2, z: z2 };
  }

  // Calculate Node Layout Coordinates (2D and 3D)
  function calculateLayout(graph) {
    const nodes = graph.nodes;
    const radius = 160;

    // 2D Circular Layout
    nodes.forEach((node, index) => {
      const angle = (index / nodes.length) * 2 * Math.PI;
      node.x = radius * Math.cos(angle);
      node.y = radius * Math.sin(angle);
    });

    // 3D Fibonacci Sphere Layout
    const phi = Math.PI * (Math.sqrt(5.0) - 1.0); // golden angle in radians
    const sphereRadius = 140;
    nodes.forEach((node, index) => {
      const y = 1.0 - (index / (nodes.length - 1 || 1)) * 2.0; // y goes from 1 to -1
      const radiusAtY = Math.sqrt(1.0 - y * y);
      const theta = phi * index;

      node.base3dX = sphereRadius * radiusAtY * Math.cos(theta);
      node.base3dY = sphereRadius * y;
      node.base3dZ = sphereRadius * radiusAtY * Math.sin(theta);

      node.rotatedX = node.base3dX;
      node.rotatedY = node.base3dY;
      node.rotatedZ = node.base3dZ;
    });
  }

  // Helper to apply opacity to colors in canvas
  function applyOpacity(color, opacity) {
    if (color.startsWith("#")) {
      const r = parseInt(color.slice(1, 3), 16);
      const g = parseInt(color.slice(3, 5), 16);
      const b = parseInt(color.slice(5, 7), 16);
      return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    }
    if (color.startsWith("rgba")) {
      return color.replace(/rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d\.]+)\s*\)/, (match, r, g, b, origOpacity) => {
        return `rgba(${r}, ${g}, ${b}, ${parseFloat(origOpacity) * opacity})`;
      });
    }
    return color;
  }

  // Draw Co-occurrence Canvas Map
  function drawGraph() {
    const canvas = document.getElementById("graph-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Update 3D rotation projections if needed
    if (state.graphMode === "3D") {
      state.graph.nodes.forEach((node) => {
        const proj = rotate3d(
          node.base3dX || 0,
          node.base3dY || 0,
          node.base3dZ || 0,
          state.graphRotation.alpha,
          state.graphRotation.beta
        );
        node.rotatedX = proj.x;
        node.rotatedY = proj.y;
        node.rotatedZ = proj.z;
      });
    }

    ctx.save();
    ctx.translate(canvas.width / 2 + state.canvasOffset.x, canvas.height / 2 + state.canvasOffset.y);

    const isEffects = document.getElementById("crt-screen").classList.contains("no-effects") === false;

    // Draw Edges (Connections)
    state.graph.edges.forEach((edge) => {
      const sourceNode = state.graph.nodes.find((n) => n.id === edge.source);
      const targetNode = state.graph.nodes.find((n) => n.id === edge.target);
      if (!sourceNode || !targetNode) return;

      const isSelected = (state.selectedEntities && state.selectedEntities.includes(edge.source)) || 
                         (state.selectedEntities && state.selectedEntities.includes(edge.target));

      let sx, sy, tx, ty;
      let opacityMultiplier = 1.0;

      if (state.graphMode === "3D") {
        sx = sourceNode.rotatedX * state.canvasScale;
        sy = sourceNode.rotatedY * state.canvasScale;
        tx = targetNode.rotatedX * state.canvasScale;
        ty = targetNode.rotatedY * state.canvasScale;

        // Fade out edges based on depth (average Z of endpoints)
        const avgZ = (sourceNode.rotatedZ + targetNode.rotatedZ) / 2;
        // sphereRadius is 140. avgZ ranges from -140 to 140.
        // Let's fade out linearly as avgZ goes from 140 to -140.
        opacityMultiplier = Math.max(0.04, Math.min(1.0, (avgZ + 120) / 200));
      } else {
        sx = sourceNode.x * state.canvasScale;
        sy = sourceNode.y * state.canvasScale;
        tx = targetNode.x * state.canvasScale;
        ty = targetNode.y * state.canvasScale;
      }

      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);

      // Selected blue color difference
      if (isSelected) {
        ctx.strokeStyle = applyOpacity("rgba(0, 210, 255, 0.7)", opacityMultiplier);
        ctx.lineWidth = Math.min(8, 2 + edge.weight * 2);
      } else {
        ctx.strokeStyle = applyOpacity("rgba(0, 255, 102, 0.15)", opacityMultiplier);
        ctx.lineWidth = Math.min(3, 0.5 + edge.weight / 2);
      }
      ctx.stroke();
    });

    // Draw Nodes (sorted by rotatedZ from back to front in 3D mode)
    let nodesToDraw = [...state.graph.nodes];
    if (state.graphMode === "3D") {
      nodesToDraw.sort((a, b) => a.rotatedZ - b.rotatedZ);
    }

    nodesToDraw.forEach((node) => {
      let depthScale = 1.0;
      let opacityMultiplier = 1.0;
      let nx, ny;

      if (state.graphMode === "3D") {
        nx = node.rotatedX * state.canvasScale;
        ny = node.rotatedY * state.canvasScale;

        // sphereRadius is 140. rotatedZ ranges from -140 to 140.
        // Scale nodes from 0.5 (back) to 1.15 (front)
        depthScale = 0.5 + 0.65 * ((node.rotatedZ + 140) / 280);
        // Fade nodes in background (Z < 0)
        opacityMultiplier = Math.max(0.12, Math.min(1.0, (node.rotatedZ + 120) / 200));
      } else {
        nx = node.x * state.canvasScale;
        ny = node.y * state.canvasScale;
      }

      const radius = (6 + Math.min(12, node.count * 1.5)) * depthScale;
      const isSelected = state.selectedEntities && state.selectedEntities.includes(node.id);
      const ch = node.channel || "generic";

      // ── Channel color scheme ──────────────────────────────────
      const channelStroke = isSelected ? "#00d2ff" :
        ch === "scene_present"       ? "#00d2ff" :
        ch === "dialogue_mentioned"  ? "#5ba3ff" :
        ch === "candidate"           ? "#ffaa00" :
        node.type === "location"     ? "#00e5ff" :
        node.type === "event"        ? "#ff6644" :
                                       "#00ff66";

      const channelFill = isSelected ? "rgba(0, 210, 255, 1.0)" :
        ch === "scene_present"       ? "rgba(0, 210, 255, 0.25)" :
        ch === "dialogue_mentioned"  ? "rgba(91, 163, 255, 0.08)" :
        ch === "candidate"           ? "rgba(255, 170, 0, 0.18)" :
                                       "rgba(2, 5, 2, 1.0)";

      const channelLabel = isSelected ? "#00d2ff" :
        ch === "scene_present"       ? "#00d2ff" :
        ch === "dialogue_mentioned"  ? "#7ab8ff" :
        ch === "candidate"           ? "#ffcc55" :
                                       "rgba(0, 255, 102, 0.85)";

      const strokeColor = applyOpacity(channelStroke, opacityMultiplier);
      const fillColor = applyOpacity(channelFill, opacityMultiplier);
      const labelColor = applyOpacity(channelLabel, opacityMultiplier);

      ctx.beginPath();

      if (ch === "candidate") {
        // Diamond for candidate/unconfirmed visible person
        ctx.moveTo(nx,          ny - radius);
        ctx.lineTo(nx + radius, ny);
        ctx.lineTo(nx,          ny + radius);
        ctx.lineTo(nx - radius, ny);
        ctx.closePath();
      } else if (node.type === "location") {
        ctx.rect(nx - radius, ny - radius, radius * 2, radius * 2);
      } else if (node.type === "event") {
        ctx.moveTo(nx, ny - radius);
        ctx.lineTo(nx + radius, ny + radius);
        ctx.lineTo(nx - radius, ny + radius);
        ctx.closePath();
      } else {
        // Circle for all person channels
        ctx.arc(nx, ny, radius, 0, 2 * Math.PI);
      }

      ctx.fillStyle = fillColor;
      ctx.fill();
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = (isSelected ? 3.5 : (ch === "scene_present" ? 2 : 1.5)) * (state.graphMode === "3D" ? depthScale : 1.0);
      ctx.stroke();

      // Glow effect (only if glows are enabled and node is not in background)
      if (isEffects && opacityMultiplier > 0.4) {
        ctx.shadowBlur = (isSelected ? 12 : (ch === "scene_present" ? 5 : 0)) * depthScale;
        ctx.shadowColor = strokeColor;
      } else {
        ctx.shadowBlur = 0;
      }

      // Text label (hide/fade on back hemisphere)
      const showLabel = !(state.graphMode === "3D" && node.rotatedZ < -10);
      if (showLabel) {
        ctx.fillStyle = labelColor;
        ctx.font = isSelected ? "bold 13px monospace" : (ch === "scene_present" ? "bold 11px monospace" : "11px monospace");
        ctx.textAlign = "center";
        ctx.fillText(node.label, nx, ny + radius + 14);
      }
    });

    ctx.restore();
  }

  // Canvas zoom/pan interpolation loop
  let animationFrameId = null;

  function animateGraph() {
    let needsRedraw = false;
    const lerpFactor = 0.08;

    const dx = state.targetOffset.x - state.canvasOffset.x;
    const dy = state.targetOffset.y - state.canvasOffset.y;
    if (Math.abs(dx) > 0.1 || Math.abs(dy) > 0.1) {
      state.canvasOffset.x += dx * lerpFactor;
      state.canvasOffset.y += dy * lerpFactor;
      needsRedraw = true;
    } else {
      state.canvasOffset.x = state.targetOffset.x;
      state.canvasOffset.y = state.targetOffset.y;
    }

    const ds = state.targetScale - state.canvasScale;
    if (Math.abs(ds) > 0.005) {
      state.canvasScale += ds * lerpFactor;
      needsRedraw = true;
    } else {
      state.canvasScale = state.targetScale;
    }

    // 3D rotation and spinning logic
    if (state.graphMode === "3D") {
      needsRedraw = true; // Always redraw in 3D mode for continuous spin/auto-rotation

      if (state.isAutoRotating && state.targetRotation) {
        // Smoothly lerp towards target rotation
        const dAlpha = state.targetRotation.alpha - state.graphRotation.alpha;
        const dBeta = state.targetRotation.beta - state.graphRotation.beta;

        // Take shortest angular path
        let deltaAlpha = ((dAlpha + Math.PI) % (2 * Math.PI)) - Math.PI;
        if (deltaAlpha < -Math.PI) deltaAlpha += 2 * Math.PI;

        let deltaBeta = ((dBeta + Math.PI) % (2 * Math.PI)) - Math.PI;
        if (deltaBeta < -Math.PI) deltaBeta += 2 * Math.PI;

        if (Math.abs(deltaAlpha) > 0.001 || Math.abs(deltaBeta) > 0.001) {
          state.graphRotation.alpha += deltaAlpha * 0.1;
          state.graphRotation.beta += deltaBeta * 0.1;
        } else {
          state.graphRotation.alpha = state.targetRotation.alpha;
          state.graphRotation.beta = state.targetRotation.beta;
          state.isAutoRotating = false;
        }
      } else if (state.isSpinning) {
        if (!state.isDragging) {
          // Spin using velocity
          state.graphRotation.alpha += state.graphSpinSpeed.alpha;
          state.graphRotation.beta += state.graphSpinSpeed.beta;

          // Gentle ambient drift speed targets
          const driftAlpha = 0.0015;
          const driftBeta = 0.0005;

          // Friction: slow down or speed up towards ambient drift speed
          state.graphSpinSpeed.alpha += (driftAlpha - state.graphSpinSpeed.alpha) * 0.05;
          state.graphSpinSpeed.beta += (driftBeta - state.graphSpinSpeed.beta) * 0.05;
        }
      }
    }

    if (needsRedraw) {
      drawGraph();
      animationFrameId = requestAnimationFrame(animateGraph);
    } else {
      animationFrameId = null;
    }
  }

  function triggerGraphAnimation() {
    if (!animationFrameId) {
      animationFrameId = requestAnimationFrame(animateGraph);
    }
  }

  // Render Video dropdown selector
  function renderVideoSelector() {
    const select = document.getElementById("dataset-select");
    if (!select) return;
    select.innerHTML = "";

    state.videos.forEach((video) => {
      const option = document.createElement("option");
      option.value = video.video_id || video.id;
      option.textContent = video.title || video.video_id || video.id;
      if (video.video_id === state.activeVideoId || video.id === state.activeVideoId) {
        option.selected = true;
      }
      select.appendChild(option);
    });
  }

  // Render Deterministic Entity Filter Checklist UI
  function renderEntityFilterChecklist(skipScrollChecklist = false) {
    const list = document.getElementById("entity-filter-list");
    if (!list) return;
    list.innerHTML = "";

    if (!state.graph || !state.graph.nodes || state.graph.nodes.length === 0) {
      const placeholder = document.createElement("span");
      placeholder.className = "placeholder-filter";
      placeholder.textContent = "No active entities loaded.";
      list.appendChild(placeholder);
      return;
    }

    // Sort entities alphabetically by label
    const sortedNodes = [...state.graph.nodes].sort((a, b) => a.label.localeCompare(b.label));

    sortedNodes.forEach((node) => {
      const isSelected = state.selectedEntities && state.selectedEntities.includes(node.id);
      
      const item = document.createElement("div");
      item.className = `entity-filter-item ${isSelected ? "selected" : ""}`;
      item.setAttribute("data-entity-id", node.id);

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = isSelected;
      
      const label = document.createElement("span");
      label.className = "entity-filter-label";
      label.textContent = `${node.label} (${node.count})`;
      
      item.appendChild(checkbox);
      item.appendChild(label);

      // Checkbox click: Toggles multi-selection state directly
      checkbox.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleSelectEntity(node.id);
      });

      // Entire row click: Single-selects (clears other selections)
      item.addEventListener("click", (e) => {
        if (e.target !== checkbox) {
          singleSelectEntity(node.id, true);
        }
      });

      // Double-click row: Deselects
      item.addEventListener("dblclick", (e) => {
        e.preventDefault();
        e.stopPropagation();
        deselectEntity(node.id);
      });

      list.appendChild(item);

      // Scroll selected item into view if not skipped
      if (isSelected && !skipScrollChecklist && node.id === state.selectedEntity) {
        setTimeout(() => {
          item.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }, 50);
      }
    });
  }

  // Render Interstellar Timeline Index Grid
  function renderTimelineGrid() {
    const grid = document.getElementById("timeline-grid");
    if (!grid) return;
    grid.innerHTML = "";

    // Dynamic concise labeling for timeline heading
    const heading = document.getElementById("timeline-heading");
    if (heading) {
      const parts = [];
      if (state.searchActive && state.lastQuery) {
        parts.push(`"${state.lastQuery}"`);
      }
      if (state.selectedEntities && state.selectedEntities.length > 0) {
        const labels = state.selectedEntities.map(id => {
          const node = state.graph.nodes.find(n => n.id === id);
          return node ? node.label : id;
        });
        parts.push(labels.join(" + "));
      }
      heading.textContent = parts.length > 0
        ? `Timeline  //  ${parts.join("  ·  ")}`
        : "Timeline  //  All Scenes";
    }

    const filteredScenes = state.scenes.filter((scene) => {
      // 1. If search is active, check if this scene is in search results
      if (state.searchActive) {
        const isMatched = state.searchResults.some((res) => res.scene_id === scene.id);
        if (!isMatched) return false;
      }

      // 2. Entity filter: check ALL channel arrays so Sprint 2 channels are included
      if (state.selectedEntities && state.selectedEntities.length > 0) {
        // Collect every entity name across all four channels
        const allChannelEntities = [
          ...(scene.entities || []),
          ...(scene.scene_present_entities || []),
          ...(scene.dialogue_mentioned_entities || []),
          ...(scene.candidate_visible_people || []),
        ];
        const sceneEntityNames = allChannelEntities.map(e =>
          typeof e === 'string' ? normalizeEntityName(e) : normalizeEntityName(e.name || '')
        );
        const hasAllSelected = state.selectedEntities.every(entityId => sceneEntityNames.includes(entityId));
        if (!hasAllSelected) return false;
      }

      return true;
    });

    filteredScenes.forEach((scene) => {
      const card = document.createElement("article");
      const isSelected = scene.id === state.selectedSceneId;
      const isMatched = state.searchResults.some((res) => res.scene_id === scene.id);

      const passesIntel = scenePassesIntelFilter(scene);
      card.className = `scene-card ${isSelected ? "selected" : ""} ${isMatched ? "matched" : ""} ${state.intelFilter && !passesIntel ? "intel-dim" : ""}`;
      card.setAttribute("data-scene-id", scene.id);

      // Keyframe thumbnail area
      const frame = document.createElement("div");
      frame.className = "scene-frame";
      if (scene.keyframe_url) {
        const img = document.createElement("img");
        img.src = `${window.location.origin}${scene.keyframe_url}`;
        img.alt = `Scene ${scene.id} keyframe`;
        img.loading = "lazy";
        frame.appendChild(img);
      } else {
        const placeholder = document.createElement("span");
        placeholder.className = "scene-frame-empty";
        placeholder.textContent = "[NO KEYFRAME]";
        frame.appendChild(placeholder);
      }

      const timeTag = document.createElement("span");
      timeTag.className = "scene-time";
      timeTag.textContent = `${formatTime(scene.start)} - ${formatTime(scene.end)}`;
      frame.appendChild(timeTag);
      card.appendChild(frame);

      // Metadata card body
      const body = document.createElement("div");
      body.className = "scene-card-body";

      const cardId = document.createElement("div");
      cardId.className = "scene-card-id";
      cardId.textContent = `SCENE #${scene.id}`;
      body.appendChild(cardId);

      const summary = document.createElement("p");
      summary.className = "scene-card-summary";
      summary.textContent = scene.summary || "No description returned.";
      body.appendChild(summary);

      // Footing info
      const footer = document.createElement("div");
      footer.className = "scene-card-footer";
      const entityCount = Array.isArray(scene.entities) ? scene.entities.length : 0;
      appendText(footer, "span", `${entityCount} Entities`);
      const dialogueCount = Array.isArray(scene.dialogue) ? scene.dialogue.length : 0;
      appendText(footer, "span", `${dialogueCount} Lines`);

      // Sentiment chip
      if (scene.sentiment_label) {
        const sl = scene.sentiment_label.toLowerCase();
        const chip = document.createElement("span");
        chip.className = `sentiment-chip ${sl === "positive" ? "positive" : sl === "negative" ? "negative" : "neutral"}`;
        chip.textContent = scene.sentiment_label.toUpperCase();
        chip.title = scene.sentiment_score != null ? `Sentiment score: ${scene.sentiment_score.toFixed(2)}` : "Sentiment";
        footer.appendChild(chip);
      }

      // Emotion badge — guard against non-string audio_emotion
      if (scene.audio_emotion && typeof scene.audio_emotion === "string") {
        const eb = document.createElement("span");
        eb.className = "emotion-badge";
        const emotionIcon = { calm: "◎", neutral: "◌", happy: "◉", joy: "◉", surprise: "◈", fear: "◆", sad: "◇", sadness: "◇", anger: "◆", disgust: "◆" };
        const emoKey = scene.audio_emotion.toLowerCase();
        const icon = emotionIcon[emoKey] || "◌";
        eb.textContent = `${icon} ${scene.audio_emotion}`;
        eb.title = `Audio emotion: ${scene.audio_emotion}`;
        footer.appendChild(eb);
      }

      // Content state dot (Sprint 4)
      const cs = (scene.content_state || "signal").toLowerCase();
      const csDot = document.createElement("span");
      csDot.className = `content-state-dot cs-${cs === "signal" ? "signal" : cs === "empty" ? "empty" : "error"}`;
      csDot.title = `Content state: ${cs}`;
      footer.appendChild(csDot);

      // Name conflict badge (Sprint 4)
      if (scene.transcript_entity_disagreements && scene.transcript_entity_disagreements.length > 0) {
        const conflictBadge = document.createElement("span");
        conflictBadge.className = "conflict-badge";
        conflictBadge.textContent = `⚠ ${scene.transcript_entity_disagreements.length}`;
        conflictBadge.title = `${scene.transcript_entity_disagreements.length} entity name conflict(s) detected`;
        footer.appendChild(conflictBadge);
      }

      card.appendChild(body);

      card.addEventListener("click", () => {
        selectScene(scene.id);
      });

      grid.appendChild(card);
    });
  }

  // Select Scene and Update Inspector (preserves entity filter)
  function selectScene(sceneId) {
    state.selectedSceneId = sceneId;
    state.selectedEntity = null;  // Clear single entity highlight but keep multi-filter
    renderTimelineGrid();
    drawGraph();
    renderInspector();
    
    // Auto-scroll timeline to target card
    const selectedCard = document.querySelector(`.scene-card[data-scene-id="${sceneId}"]`);
    if (selectedCard) {
      selectedCard.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }

  // Single Select an Entity (clears other selections)
  function singleSelectEntity(entityId, skipScrollChecklist = false) {
    state.selectedEntities = [entityId];
    state.selectedEntity = entityId;
    state.selectedSceneId = null;

    // Zoom and center graph canvas on this node
    const canvas = document.getElementById("graph-canvas");
    if (canvas && state.selectedEntity) {
      const node = state.graph.nodes.find((n) => n.id === state.selectedEntity);
      if (node) {
        if (state.graphMode === "3D") {
          const alpha = -Math.atan2(node.base3dX || 0, node.base3dZ || 0);
          const beta = -Math.atan2(node.base3dY || 0, Math.hypot(node.base3dX || 0, node.base3dZ || 0));

          state.targetRotation = { alpha, beta };
          state.graphSpinSpeed = { alpha: 0, beta: 0 };
          state.isAutoRotating = true;

          const projected = rotate3d(node.base3dX || 0, node.base3dY || 0, node.base3dZ || 0, alpha, beta);
          state.targetScale = 1.8;
          state.targetOffset.x = -projected.x * 1.8;
          state.targetOffset.y = -projected.y * 1.8;
        } else {
          state.targetScale = 1.8;
          state.targetOffset.x = -node.x * 1.8;
          state.targetOffset.y = -node.y * 1.8;
        }
        triggerGraphAnimation();
      }
    }

    renderTimelineGrid();
    drawGraph();
    renderInspector();
    renderEntityFilterChecklist(skipScrollChecklist);
  }

  // Toggle selection for multi-filtering (triggered by clicking checkboxes directly)
  function toggleSelectEntity(entityId) {
    if (!state.selectedEntities) {
      state.selectedEntities = [];
    }
    const idx = state.selectedEntities.indexOf(entityId);
    if (idx > -1) {
      state.selectedEntities.splice(idx, 1);
    } else {
      state.selectedEntities.push(entityId);
    }

    state.selectedEntity = state.selectedEntities.length > 0 ? state.selectedEntities[state.selectedEntities.length - 1] : null;
    state.selectedSceneId = null;

    // Zoom and center graph canvas on latest selected node
    const canvas = document.getElementById("graph-canvas");
    if (canvas && state.selectedEntity) {
      const node = state.graph.nodes.find((n) => n.id === state.selectedEntity);
      if (node) {
        if (state.graphMode === "3D") {
          const alpha = -Math.atan2(node.base3dX || 0, node.base3dZ || 0);
          const beta = -Math.atan2(node.base3dY || 0, Math.hypot(node.base3dX || 0, node.base3dZ || 0));

          state.targetRotation = { alpha, beta };
          state.graphSpinSpeed = { alpha: 0, beta: 0 };
          state.isAutoRotating = true;

          const projected = rotate3d(node.base3dX || 0, node.base3dY || 0, node.base3dZ || 0, alpha, beta);
          state.targetScale = 1.8;
          state.targetOffset.x = -projected.x * 1.8;
          state.targetOffset.y = -projected.y * 1.8;
        } else {
          state.targetScale = 1.8;
          state.targetOffset.x = -node.x * 1.8;
          state.targetOffset.y = -node.y * 1.8;
        }
        triggerGraphAnimation();
      }
    }

    renderTimelineGrid();
    drawGraph();
    renderInspector();
    renderEntityFilterChecklist(true);
  }

  // Deselect a specific Entity
  function deselectEntity(entityId) {
    if (!state.selectedEntities) {
      state.selectedEntities = [];
    }
    state.selectedEntities = state.selectedEntities.filter(id => id !== entityId);
    state.selectedEntity = state.selectedEntities.length > 0 ? state.selectedEntities[state.selectedEntities.length - 1] : null;
    state.selectedSceneId = null;

    renderTimelineGrid();
    drawGraph();
    renderInspector();
    renderEntityFilterChecklist(false);
  }

  // Reset Entity Filters Only (preserves search query/results)
  function resetEntityFilters() {
    state.selectedEntity = null;
    state.selectedEntities = [];
    state.selectedSceneId = null;
    state.targetScale = 1.0;
    state.targetOffset = { x: 0, y: 0 };
    triggerGraphAnimation();
    renderTimelineGrid();
    drawGraph();
    renderInspector();
    renderEntityFilterChecklist(false);
  }

  // Reset Only Entity Filters (keeps scene selection and search)
  function resetEntityFilters() {
    state.selectedEntity = null;
    state.selectedEntities = [];
    state.targetScale = 1.0;
    state.targetOffset = { x: 0, y: 0 };
    triggerGraphAnimation();
    renderTimelineGrid();
    drawGraph();
    renderInspector();
    renderEntityFilterChecklist(false);
  }

  // Reset All Filters (Search + entities + zoom)
  function resetAllFilters() {
    state.selectedEntity = null;
    state.selectedEntities = [];
    state.selectedSceneId = null;
    state.searchResults = [];
    state.searchActive = false;
    const queryInput = document.getElementById("query-input");
    if (queryInput) queryInput.value = "";
    state.targetScale = 1.0;
    state.targetOffset = { x: 0, y: 0 };
    triggerGraphAnimation();
    renderTimelineGrid();
    drawGraph();
    renderInspector();
    renderEntityFilterChecklist(false);
  }

  // Select Entity - single select backwards compatible wrapper
  function selectEntity(entityId, skipScrollChecklist = false) {
    singleSelectEntity(entityId, skipScrollChecklist);
  }

  // Render Metadata Detail Inspector Panel
  function renderInspector() {
    const defaultMsg = document.getElementById("inspector-default-message");
    const details = document.getElementById("inspector-details");
    const subResizer = document.getElementById("resizer-subsection");
    const keyframeZone = document.getElementById("inspector-keyframe-zone");
    const keyframeActive = document.getElementById("inspector-keyframe-active");
    const keyframeImg = document.getElementById("inspector-keyframe-img");
    const keyframeTimecode = document.getElementById("inspector-keyframe-timecode");
    const keyframeNoImage = document.getElementById("inspector-keyframe-no-image");
    const noKeyframeTitle = document.getElementById("no-keyframe-title");
    const noKeyframeText = document.getElementById("no-keyframe-text");
    const transcriptZone = document.getElementById("inspector-transcript-zone");

    if (!defaultMsg || !details) return;

    // Reset zones
    if (keyframeZone) keyframeZone.hidden = false;
    if (keyframeActive) keyframeActive.hidden = true;
    if (transcriptZone) {
      transcriptZone.innerHTML = "";
      transcriptZone.hidden = true;
    }

    if (!state.selectedSceneId && !state.selectedEntity) {
      defaultMsg.hidden = false;
      details.hidden = true;
      if (subResizer) subResizer.style.display = "none";
      return;
    }

    defaultMsg.hidden = true;
    details.hidden = false;
    if (subResizer) {
      const dataTrailSection = document.getElementById("data-trail-section");
      const isCollapsed = dataTrailSection && dataTrailSection.classList.contains("collapsed");
      subResizer.style.display = isCollapsed ? "none" : "";
    }
    details.innerHTML = "";

    // Case 1: Active Entity Node Selection
    if (state.selectedEntity) {
      if (keyframeZone) keyframeZone.hidden = true;
      if (transcriptZone) {
        transcriptZone.innerHTML = "";
        transcriptZone.hidden = true;
      }
      const node = state.graph.nodes.find((n) => n.id === state.selectedEntity);
      if (!node) return;

      const header = document.createElement("div");
      header.className = "details-header";
      appendText(header, "h3", `Entity: ${node.label}`, "details-title");
      appendText(header, "p", `Category: ${node.type.toUpperCase()}`, "details-subtitle");
      details.appendChild(header);

      const countInfo = document.createElement("div");
      countInfo.className = "details-summary";
      countInfo.textContent = `Entity Co-occurrence Map counts: This entity appears in ${node.count} scene${node.count === 1 ? "" : "s"} across the timeline.`;
      details.appendChild(countInfo);

      // List related entities (co-occurrences)
      const cooccurrences = state.graph.edges
        .filter((e) => e.source === node.id || e.target === node.id)
        .map((e) => {
          const otherId = e.source === node.id ? e.target : e.source;
          const otherNode = state.graph.nodes.find((n) => n.id === otherId);
          return {
            id: otherId,
            label: otherNode ? otherNode.label : otherId,
            weight: e.weight,
            type: otherNode ? otherNode.type : "generic",
          };
        })
        .sort((a, b) => b.weight - a.weight);

      if (cooccurrences.length) {
        appendText(details, "h4", "Entity Co-occurrence Grid");
        const list = document.createElement("div");
        list.className = "details-entities-list";
        cooccurrences.forEach((co) => {
          const pill = document.createElement("span");
          pill.className = `entity-pill ${co.type}`;
          pill.textContent = `${co.label} (Appears together in ${co.weight} scene${co.weight === 1 ? "" : "s"})`;
          pill.addEventListener("click", (e) => {
            e.stopPropagation();
            singleSelectEntity(co.id);
          });
          pill.addEventListener("dblclick", (e) => {
            e.stopPropagation();
            deselectEntity(co.id);
          });
          list.appendChild(pill);
        });
        details.appendChild(list);
      }

      // Show filter trigger
      const filterBtn = document.createElement("button");
      filterBtn.className = "retro-btn primary-btn";
      filterBtn.textContent = "Highlight Scenes in Grid";
      filterBtn.addEventListener("click", () => {
        state.searchResults = node.sceneIds.map((sid) => ({ scene_id: sid }));
        renderTimelineGrid();
        logDataTrail(
          `Filter grid by entity: "${node.label}"`,
          "Internal UI Event",
          state.activeVideoId,
          "scene metadata",
          `Highlighted ${node.sceneIds.length} scenes containing "${node.label}"`,
          1.0,
          ""
        );
      });
      details.appendChild(filterBtn);
      return;
    }

    // Case 2: Active Scene Selection
    const scene = state.scenes.find((s) => s.id === state.selectedSceneId);
    if (!scene) return;

    // Render keyframe active state
    if (keyframeZone) keyframeZone.hidden = false;
    if (keyframeActive) keyframeActive.hidden = false;

    if (scene.keyframe_url) {
      if (keyframeImg) {
        keyframeImg.src = `${window.location.origin}${scene.keyframe_url}`;
        keyframeImg.alt = `Scene ${scene.id} keyframe`;
        keyframeImg.style.display = "block";
      }
      if (keyframeNoImage) keyframeNoImage.hidden = true;
    } else {
      if (keyframeImg) {
        keyframeImg.src = "";
        keyframeImg.style.display = "none";
      }
      if (keyframeNoImage) {
        keyframeNoImage.hidden = false;
        if (noKeyframeTitle) noKeyframeTitle.textContent = `NO VISUAL CARRIER // SCENE #${scene.id}`;
        if (noKeyframeText) noKeyframeText.textContent = `TIMECODE: ${formatTime(scene.start)} - ${formatTime(scene.end)}`;
      }
    }

    if (keyframeTimecode) {
      keyframeTimecode.textContent = `${formatTime(scene.start)} - ${formatTime(scene.end)}`;
    }

    const header = document.createElement("div");
    header.className = "details-header";
    appendText(header, "h3", `SCENE INDEX #${scene.id}`, "details-title");
    appendText(header, "p", `Timecode: ${formatTime(scene.start)} - ${formatTime(scene.end)}`, "details-subtitle");
    details.appendChild(header);

    // ── Scene Context LLM (tag groups: primary_tags / contextual_tags / structural_tags) ──
    const ctx_llm = scene.scene_context_llm;
    const ctx_epistemic = scene.scene_context_epistemic;
    if (ctx_llm && typeof ctx_llm === "object") {
      const ctxWrap = document.createElement("div");
      ctxWrap.className = "scene-context-wrap";

      const ctxHeader = document.createElement("div");
      ctxHeader.className = "scene-context-header";
      const ctxLabel = document.createElement("h4");
      ctxLabel.textContent = "Scene Context";
      ctxLabel.style.marginBottom = "0";
      ctxHeader.appendChild(ctxLabel);

      // Epistemic state badge — actual field uses top-level .state (simplified internal format)
      // per _derive_scene_context_epistemic in cross_modal_harmonizer.py:
      // { state, dominant_evidence, evidence_family, fallback_mode, conflict_detected, evidence, limits, next_steps }
      let epistemicState = null;
      if (ctx_epistemic && typeof ctx_epistemic === "object") {
        // Prefer top-level .state (internal simplified format)
        epistemicState = ctx_epistemic.state || ctx_epistemic.epistemic_state || null;
        // Fallback: EpistemicReadEnvelope format (candidates[0].state)
        if (!epistemicState) {
          const candidates = Array.isArray(ctx_epistemic.candidates) ? ctx_epistemic.candidates : [];
          if (candidates.length > 0 && candidates[0].state) epistemicState = candidates[0].state;
        }
        if (!epistemicState && ctx_epistemic.dont_know) epistemicState = ctx_epistemic.dont_know.state || null;
      }
      if (epistemicState) {
        const badge = document.createElement("span");
        const es = epistemicState.toLowerCase();
        badge.className = `epistemic-badge ${
          es === "supported"                ? "supported" :
          es === "partially_supported"      ? "inferred" :
          es === "conflicted"               ? "conflict" :
          es === "stale"                    ? "uncertain" :
          es === "unsupported_but_related"  ? "uncertain" :
                                             "uncertain"
        }`;
        badge.textContent = epistemicState.replace(/_/g, " ").toUpperCase();
        badge.title = "Epistemic confidence state for this scene";
        ctxHeader.appendChild(badge);
      }

      // Sprint 4 (P2): scene_context_arbitration resolved_by badge
      const arb = scene.scene_context_arbitration;
      if (arb && typeof arb === "object" && arb.resolved_by) {
        const arbBadge = document.createElement("span");
        arbBadge.className = "arbitration-badge";
        arbBadge.textContent = `resolved: ${String(arb.resolved_by).replace(/_/g, " ")}`;
        arbBadge.title = arb.unresolved_axes && arb.unresolved_axes.length
          ? `Unresolved axes: ${arb.unresolved_axes.join(", ")}`
          : "No unresolved axes";
        ctxHeader.appendChild(arbBadge);
      }
      ctxWrap.appendChild(ctxHeader);

      // Render {primary_tags, contextual_tags, structural_tags} as labelled pill groups
      const tagGroups = [
        { key: "primary_tags",     label: "Primary" },
        { key: "contextual_tags",  label: "Context" },
        { key: "structural_tags",  label: "Structure" },
      ];
      let hasAnyTags = false;
      tagGroups.forEach(({ key, label }) => {
        const tags = Array.isArray(ctx_llm[key]) ? ctx_llm[key] : [];
        if (!tags.length) return;
        hasAnyTags = true;
        const groupRow = document.createElement("div");
        groupRow.className = "ctx-tag-group";
        const groupLabel = document.createElement("span");
        groupLabel.className = "ctx-tag-label";
        groupLabel.textContent = label + ":";
        groupRow.appendChild(groupLabel);
        tags.forEach((tag) => {
          const chip = document.createElement("span");
          chip.className = `scene-tag ctx-tag-${key.replace(/_tags$/, "")}`;
          chip.textContent = typeof tag === "string" ? tag : (tag.label || String(tag));
          groupRow.appendChild(chip);
        });
        ctxWrap.appendChild(groupRow);
      });
      // Fallback: if none of the three tag arrays exist, show raw text if it's a string
      if (!hasAnyTags && typeof ctx_llm === "string") {
        const ctxText = document.createElement("p");
        ctxText.className = "scene-context-block";
        ctxText.textContent = ctx_llm;
        ctxWrap.appendChild(ctxText);
      }
      details.appendChild(ctxWrap);
    }

    const summary = document.createElement("div");
    summary.className = "details-summary";
    summary.textContent = scene.summary || "No description available.";
    details.appendChild(summary);

    // Metadata grid details
    const dl = document.createElement("dl");
    dl.className = "details-metadata";
    [
      ["Duration", `${Math.round(scene.end - scene.start)} seconds`],
      ["Start Offset", `${scene.start}s`],
      ["End Offset", `${scene.end}s`],
    ].forEach(([k, v]) => {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    details.appendChild(dl);

    // Scene entities — split into channel groups
    const scenePresent  = scene.scene_present_entities  || [];
    const mentioned     = scene.dialogue_mentioned_entities || [];
    const candidates    = scene.candidate_visible_people || [];
    const fallbackAll   = scene.entities || [];

    // Helper: render one channel group of entity pills (const arrow avoids strict-mode block-fn issue)
    const renderEntityGroup = (heading, list, pillClass, enableSelect) => {
      if (!list.length) return;
      appendText(details, "h4", heading);
      const grp = document.createElement("div");
      grp.className = "details-entities-list";
      list.forEach((entity) => {
        const pill = document.createElement("span");
        pill.className = `entity-pill ${pillClass}`;
        pill.textContent = formatEntityLabel(entity);
        if (enableSelect) {
          pill.style.cursor = "pointer";
          pill.addEventListener("click", (e) => {
            e.stopPropagation();
            singleSelectEntity(normalizeEntityName(entity.name || entity));
          });
          pill.addEventListener("dblclick", (e) => {
            e.stopPropagation();
            deselectEntity(normalizeEntityName(entity.name || entity));
          });
        } else {
          pill.style.cursor = "default";
        }
        grp.appendChild(pill);
      });
      details.appendChild(grp);
    };

    const hasChannels = scenePresent.length || mentioned.length || candidates.length;
    if (hasChannels) {
      renderEntityGroup("In Scene (Proven)", scenePresent, "scene-present", true);
      renderEntityGroup("Mentioned in Dialogue", mentioned, "mentioned", true);
      renderEntityGroup("Visible / Unconfirmed", candidates, "candidate-visible", false);
    } else if (fallbackAll.length) {
      // Fallback: render merged entities list when no channels populated
      appendText(details, "h4", "Detected Entities");
      const list = document.createElement("div");
      list.className = "details-entities-list";
      fallbackAll.forEach((entity) => {
        const pill = document.createElement("span");
        pill.className = `entity-pill ${entity.type || ""}`;
        pill.textContent = formatEntityLabel(entity);
        pill.addEventListener("click", (e) => {
          e.stopPropagation();
          singleSelectEntity(normalizeEntityName(entity.name || entity));
        });
        pill.addEventListener("dblclick", (e) => {
          e.stopPropagation();
          deselectEntity(normalizeEntityName(entity.name || entity));
        });
        list.appendChild(pill);
      });
      details.appendChild(list);
    }

    // ── Sprint 4 (P2): Keywords ───────────────────────────────────
    if (scene.keywords && scene.keywords.length > 0) {
      appendText(details, "h4", "Keywords");
      const kwRow = document.createElement("div");
      kwRow.className = "details-entities-list keywords-list";
      scene.keywords.forEach((kw) => {
        const pill = document.createElement("span");
        pill.className = "keyword-pill";
        pill.textContent = typeof kw === "string" ? kw : String(kw);
        kwRow.appendChild(pill);
      });
      details.appendChild(kwRow);
    }

    // ── Detected Objects (separate from people/entity pills) ──────
    if (scene.objects && scene.objects.length > 0) {
      appendText(details, "h4", "Detected Objects");
      const objList = document.createElement("div");
      objList.className = "details-entities-list objects-list";
      scene.objects.forEach((label) => {
        const pill = document.createElement("span");
        pill.className = "entity-pill object-pill";
        pill.textContent = label;
        pill.title = `Detected object: ${label}`;
        objList.appendChild(pill);
      });
      details.appendChild(objList);
    }

    // ── P1: Time Hints + P2: OCR Date Candidates ─────────────────
    const hasTimeHints = scene.time_hints && typeof scene.time_hints === "object";
    const hasOcrDates = scene.ocr_date_candidates && scene.ocr_date_candidates.length > 0;
    if (hasTimeHints || hasOcrDates) {
      const SYSTEM_KEYS = new Set(["first_seen_ts"]);
      const hintEntries = hasTimeHints
        ? Object.entries(scene.time_hints)
            .filter(([k, v]) => !SYSTEM_KEYS.has(k) && v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length))
            .map(([k, v]) => [k.replace(/_/g, " "), Array.isArray(v) ? v.join(", ") : String(v)])
        : [];

      // Merge OCR date candidates into hint display
      const dateEntries = hasOcrDates
        ? scene.ocr_date_candidates.map(d => ["ocr date", String(d)])
        : [];

      const allEntries = [...hintEntries, ...dateEntries];
      if (allEntries.length > 0) {
        appendText(details, "h4", "Time Hints");
        const hintsRow = document.createElement("div");
        hintsRow.className = "time-hints-row";
        hintEntries.forEach(([key, val]) => {
          const pill = document.createElement("span");
          pill.className = "time-hint-pill";
          pill.textContent = `${key}: ${val}`;
          hintsRow.appendChild(pill);
        });
        dateEntries.forEach(([, val]) => {
          const pill = document.createElement("span");
          pill.className = "time-hint-pill ocr-date";
          pill.textContent = `📅 ${val}`;
          pill.title = "OCR-extracted date candidate";
          hintsRow.appendChild(pill);
        });
        details.appendChild(hintsRow);
      }
    }

    // ── P1: Conversation Dynamics (interaction_dominance + conversation_owner + speaker_aligned_mentions) ─
    const hasDynamics = scene.interaction_dominance || scene.conversation_owner ||
      (scene.speaker_aligned_mentions && scene.speaker_aligned_mentions.length > 0);

    if (hasDynamics) {
      appendText(details, "h4", "Conversation Dynamics");
      const dynWrap = document.createElement("div");
      dynWrap.className = "conv-dynamics-wrap";

      // interaction_dominance: { speaker_id, dominant_share, segments, stability, confidence, continuity_key }
      if (scene.interaction_dominance && typeof scene.interaction_dominance === "object") {
        const dom = scene.interaction_dominance;
        const domRow = document.createElement("div");
        domRow.className = "conv-dynamics-row";
        const domLabel = document.createElement("span");
        domLabel.className = "conv-dynamics-label";
        domLabel.textContent = "Dominant Speaker:";
        domRow.appendChild(domLabel);

        const speakerId = dom.speaker_id || dom.dominant_speaker_id || "?";
        const share = typeof dom.dominant_share === "number" ? `${(dom.dominant_share * 100).toFixed(0)}%` : null;
        const conf = dom.confidence || null;
        const stability = typeof dom.stability === "number" ? `stability ${(dom.stability * 100).toFixed(0)}%` : null;
        // P2: speaker_count
        const spkCount = typeof scene.speaker_count === "number" ? `${scene.speaker_count} spk` : null;

        const speakerChip = document.createElement("span");
        speakerChip.className = "speaker-id-chip";
        speakerChip.textContent = speakerId;
        speakerChip.title = "Structural speaker label — not an identity claim";
        domRow.appendChild(speakerChip);

        [share, conf, stability, spkCount].filter(Boolean).forEach(detail => {
          const detailChip = document.createElement("span");
          detailChip.className = `conv-detail-chip${conf === detail ? (detail === "strong" ? " strong" : " stable") : ""}`;
          detailChip.textContent = detail;
          domRow.appendChild(detailChip);
        });
        dynWrap.appendChild(domRow);
      }

      // conversation_owner: { name, text, type, confidence, mention_dominance_ratio, chain_length, ... }
      if (scene.conversation_owner && typeof scene.conversation_owner === "object") {
        const owner = scene.conversation_owner;
        const ownerName = owner.name || owner.text || null;
        if (ownerName) {
          const ownerRow = document.createElement("div");
          ownerRow.className = "conv-dynamics-row";
          const ownerLabel = document.createElement("span");
          ownerLabel.className = "conv-dynamics-label";
          ownerLabel.textContent = "Conversation About:";
          ownerRow.appendChild(ownerLabel);

          const ownerChip = document.createElement("span");
          ownerChip.className = "entity-pill candidate-visible";
          ownerChip.textContent = ownerName;
          const mentionRatio = typeof owner.mention_dominance_ratio === "number"
            ? `${(owner.mention_dominance_ratio * 100).toFixed(0)}% of mentions` : null;
          const chainLen = typeof owner.chain_length === "number" ? `${owner.chain_length}-scene chain` : null;
          ownerChip.title = [
            `Source: ${owner.source || "interaction_chain"}`,
            mentionRatio,
            chainLen,
            `Confidence: ${owner.confidence || "candidate"}`,
          ].filter(Boolean).join(" · ");
          ownerChip.style.cursor = "pointer";
          ownerChip.addEventListener("click", (e) => {
            e.stopPropagation();
            singleSelectEntity(normalizeEntityName(ownerName));
          });
          ownerRow.appendChild(ownerChip);

          if (mentionRatio) {
            const ratioChip = document.createElement("span");
            ratioChip.className = "conv-detail-chip";
            ratioChip.textContent = mentionRatio;
            ownerRow.appendChild(ratioChip);
          }
          dynWrap.appendChild(ownerRow);
        }
      }

      // speaker_aligned_mentions: [{ text, type, count }] — who the dominant speaker mentioned
      if (scene.speaker_aligned_mentions && scene.speaker_aligned_mentions.length > 0) {
        const mentionRow = document.createElement("div");
        mentionRow.className = "conv-dynamics-row";
        const mentionLabel = document.createElement("span");
        mentionLabel.className = "conv-dynamics-label";
        mentionLabel.textContent = "Speaker Mentions:";
        mentionRow.appendChild(mentionLabel);
        scene.speaker_aligned_mentions.forEach((mention) => {
          const name = mention.text || mention.name || "";
          if (!name) return;
          const chip = document.createElement("span");
          chip.className = "entity-pill mentioned";
          chip.textContent = mention.count > 1 ? `${name} ×${mention.count}` : name;
          chip.title = `Mentioned ${mention.count || 1}× by dominant speaker in this scene`;
          chip.style.cursor = "pointer";
          chip.addEventListener("click", (e) => {
            e.stopPropagation();
            singleSelectEntity(normalizeEntityName(name));
          });
          mentionRow.appendChild(chip);
        });
        dynWrap.appendChild(mentionRow);
      }

      details.appendChild(dynWrap);
    }

    // ── Sprint 4 (P2): Transcript Entity Disagreements ───────────
    if (scene.transcript_entity_disagreements && scene.transcript_entity_disagreements.length > 0) {
      const disags = scene.transcript_entity_disagreements;
      const disagSection = document.createElement("div");
      disagSection.className = "disag-section";

      const disagHeader = document.createElement("div");
      disagHeader.className = "disag-header";
      const disagTitle = document.createElement("h4");
      disagTitle.textContent = `⚠ Name Conflicts (${disags.length})`;
      disagTitle.style.color = "rgba(255,180,0,0.85)";
      disagTitle.style.margin = "0";
      disagHeader.appendChild(disagTitle);

      const disagToggle = document.createElement("button");
      disagToggle.className = "disag-toggle-btn";
      disagToggle.textContent = "Show";
      disagHeader.appendChild(disagToggle);
      disagSection.appendChild(disagHeader);

      const disagTable = document.createElement("div");
      disagTable.className = "disag-table";
      disagTable.hidden = true;
      disags.forEach((d) => {
        const row = document.createElement("div");
        row.className = "disag-row";
        // transcript_candidate: surface form found in transcript
        // entity_names: person entity list for this segment (string[])
        // reason: human-readable description of the conflict type
        const candidate = d.transcript_candidate || d.candidate || "?";
        const inScene = Array.isArray(d.entity_names) ? d.entity_names.join(" / ") : String(d.entity_names || "?");
        const reason = (d.reason || d.category || "").replace(/_/g, " ");

        const spanCandidate = document.createElement("span");
        spanCandidate.className = "disag-candidate";
        spanCandidate.textContent = candidate;
        spanCandidate.title = `Transcript surface: "${candidate}"`;

        const spanArrow = document.createElement("span");
        spanArrow.className = "disag-arrow";
        spanArrow.textContent = "→";

        const spanMatched = document.createElement("span");
        spanMatched.className = "disag-matched";
        spanMatched.textContent = inScene;
        spanMatched.title = `People in scene: ${inScene}`;

        const spanReason = document.createElement("span");
        spanReason.className = "disag-reason";
        spanReason.textContent = reason;
        spanReason.title = reason;

        row.appendChild(spanCandidate);
        row.appendChild(spanArrow);
        row.appendChild(spanMatched);
        row.appendChild(spanReason);
        disagTable.appendChild(row);
      });

      disagToggle.addEventListener("click", () => {
        const hidden = disagTable.hidden;
        disagTable.hidden = !hidden;
        disagToggle.textContent = hidden ? "Hide" : "Show";
      });
      disagSection.appendChild(disagTable);
      details.appendChild(disagSection);
    }

    // ── Transcript ─────────────────────────────────────────────────────────────
    if (scene.tags && scene.tags.length > 0) {
      const tagsRow = document.createElement("div");
      tagsRow.className = "scene-tags-row";
      scene.tags.forEach((tag) => {
        const t = document.createElement("span");
        t.className = "scene-tag";
        t.textContent = typeof tag === "string" ? tag : (tag.label || tag.name || String(tag));
        tagsRow.appendChild(t);
      });
      details.appendChild(tagsRow);
    }

    // ── Emotion + Sentiment Summary Row ──────────────────────────
    const hasEmotionData = scene.audio_emotion || (scene.audio_emotion_ranking && scene.audio_emotion_ranking.length > 0)
                        || (scene.text_emotion_ranking && scene.text_emotion_ranking.length > 0);
    if (hasEmotionData || scene.sentiment_label) {
      const emoRow = document.createElement("div");
      emoRow.className = "inspector-emo-row";

      // Sentiment chip
      if (scene.sentiment_label) {
        const sl = scene.sentiment_label.toLowerCase();
        const chip = document.createElement("span");
        chip.className = `sentiment-chip ${sl === "positive" ? "positive" : sl === "negative" ? "negative" : "neutral"}`;
        chip.textContent = scene.sentiment_label.toUpperCase();
        if (scene.sentiment_score != null) chip.title = `Score: ${scene.sentiment_score.toFixed(2)}`;
        emoRow.appendChild(chip);
      }

      // ── Audio emotion ─────────────────────────────────────────
      if (scene.audio_emotion_ranking && scene.audio_emotion_ranking.length > 0) {
        // Label row header
        const audioHdr = document.createElement("span");
        audioHdr.className = "emo-channel-label";
        audioHdr.textContent = "Audio:";
        emoRow.appendChild(audioHdr);

        scene.audio_emotion_ranking.slice(0, 3).forEach((entry, idx) => {
          const label = entry.label || entry;
          const score = typeof entry.score === "number" ? entry.score : null;
          const eb = document.createElement("span");
          // audio_emotion null means threshold not met — top ranked shown with tilde
          const isPromoted = scene.audio_emotion && scene.audio_emotion.toLowerCase() === String(label).toLowerCase();
          eb.className = `emotion-badge${isPromoted ? " promoted" : " candidate"}`;
          eb.textContent = (idx === 0 && !isPromoted) ? `~${label}` : label;
          if (score != null) eb.title = `Audio emotion score: ${(score * 100).toFixed(0)}%${!isPromoted ? " (below promotion threshold)" : ""}`;
          emoRow.appendChild(eb);
        });
      } else if (scene.audio_emotion) {
        const eb = document.createElement("span");
        eb.className = "emotion-badge promoted";
        eb.textContent = scene.audio_emotion;
        emoRow.appendChild(eb);
      }

      // ── Text emotion (CardiffNLP) ──────────────────────────────
      if (scene.text_emotion_ranking && scene.text_emotion_ranking.length > 0) {
        const textHdr = document.createElement("span");
        textHdr.className = "emo-channel-label";
        textHdr.textContent = "Text:";
        emoRow.appendChild(textHdr);

        scene.text_emotion_ranking.slice(0, 3).forEach((entry) => {
          const label = entry.label || entry;
          const score = typeof entry.score === "number" ? entry.score : null;
          const eb = document.createElement("span");
          eb.className = "emotion-badge text-emotion";
          eb.textContent = label;
          if (score != null) eb.title = `Text emotion score: ${(score * 100).toFixed(0)}%`;
          emoRow.appendChild(eb);
        });
      }

      details.appendChild(emoRow);
    }

    // ── Visual Caption ────────────────────────────────────────────
    if (scene.visual_caption) {
      appendText(details, "h4", "Visual Description");
      const captionBlock = document.createElement("p");
      captionBlock.className = "visual-caption-block";
      captionBlock.textContent = scene.visual_caption;
      details.appendChild(captionBlock);
    }

    // ── OCR / Screen Text ─────────────────────────────────────────
    if (scene.ocr_text && scene.ocr_text.trim().length > 2) {
      appendText(details, "h4", "Screen Text (OCR)");
      const ocrBlock = document.createElement("pre");
      ocrBlock.className = "ocr-text-block";
      ocrBlock.textContent = scene.ocr_text.trim();
      details.appendChild(ocrBlock);
    }

    // Scene transcripts / dialogue list with TTS controls
    const lines = scene.dialogue || [];
    if (lines.length) {
      // Transcript heading row with Play All button
      const transcriptHeader = document.createElement("div");
      transcriptHeader.className = "transcript-header";
      const transcriptLabel = document.createElement("h4");
      transcriptLabel.textContent = "Scene Transcript";
      transcriptHeader.appendChild(transcriptLabel);

      const playAllBtn = document.createElement("button");
      playAllBtn.className = "tts-play-all-btn";
      playAllBtn.textContent = tts.supported ? "▶ PLAY ALL" : "TTS N/A";
      playAllBtn.disabled = !tts.supported;
      playAllBtn.title = "Read full transcript aloud";
      transcriptHeader.appendChild(playAllBtn);

      // Voice picker dropdown
      if (tts.supported && tts.voices.length > 0) {
        const enVoices = tts.voices.filter(v => v.lang.startsWith('en'));
        if (enVoices.length > 0) {
          const picker = document.createElement("select");
          picker.className = "tts-voice-picker";
          picker.title = "Select TTS voice";
          enVoices.forEach(v => {
            const opt = document.createElement("option");
            opt.value = v.name;
            opt.textContent = ttsVoiceLabel(v);
            if (tts.voice && tts.voice.name === v.name) opt.selected = true;
            picker.appendChild(opt);
          });
          picker.addEventListener("change", () => {
            tts.voice = tts.voices.find(v => v.name === picker.value) || null;
            ttsStop();
          });
          transcriptHeader.appendChild(picker);
        }
      }


      const container = document.createElement("div");
      container.className = "scene-transcript-box";

      if (tts.supported) {
        const hint = document.createElement("span");
        hint.className = "tts-hint";
        hint.textContent = "Select any text to speak it";
        container.appendChild(hint);
      }

      // Collect row metadata for play-all sequencing
      const rowMeta = [];

      lines.forEach((line) => {
        const row = document.createElement("div");
        row.className = "transcript-row";

        // Per-line play button
        let rowBtn = null;
        if (tts.supported) {
          rowBtn = document.createElement("button");
          rowBtn.className = "tts-btn";
          rowBtn.textContent = "▶";
          rowBtn.title = `Read line aloud`;
          row.appendChild(rowBtn);
        }

        const speaker = document.createElement("strong");
        speaker.className = "transcript-speaker";
        speaker.textContent = `${line.speaker}: `;
        row.appendChild(speaker);

        const textSpan = document.createElement("span");
        textSpan.className = "transcript-text";
        textSpan.textContent = line.text;
        row.appendChild(textSpan);

        container.appendChild(row);

        const speakText = `${line.speaker} says: ${line.text}`;
        rowMeta.push({ rowEl: row, rowBtn, text: speakText });

        if (rowBtn) {
          rowBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            ttsPlayRow(row, rowBtn, speakText);
          });
        }
      });

      // Play All button handler
      playAllBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        ttsPlayAll(rowMeta, playAllBtn);
      });

      // Highlight-to-speak: speak selected text on mouseup inside transcript box
      if (tts.supported) {
        container.addEventListener("mouseup", () => {
          const sel = window.getSelection();
          const selected = sel ? sel.toString().trim() : "";
          if (selected.length > 2) {
            ttsStop();
            ttsSpeak(selected);
          }
        });
      }

      // Wrap header + transcript box in a dedicated zone for proper layout
      const tZone = document.getElementById("inspector-transcript-zone");
      if (tZone) {
        tZone.innerHTML = "";
        tZone.hidden = false;
        tZone.appendChild(transcriptHeader);
        tZone.appendChild(container);
      }
    }
  }

  // Format entity labels neatly
  function formatEntityLabel(entity) {
    if (typeof entity === "string") return entity;
    const text = entity.name || entity.label || "generic";
    return entity.type ? `${text} (${entity.type})` : text;
  }

  // Log Data Trail events (Forensic logging)
  function logDataTrail(query, endpoint, dataset, source, reason, confidence, timeRange) {
    const container = document.getElementById("data-trail-logs");
    if (!container) return;

    // Remove placeholder on first log
    const placeholder = container.querySelector(".placeholder-log");
    if (placeholder) placeholder.remove();

    const row = document.createElement("div");
    row.className = "data-trail-row";

    const fields = [
      ["Query", query],
      ["Endpoint", endpoint],
      ["Dataset", dataset],
      ["Evidence source", source],
      ["Match reason", reason],
      ["Confidence", confidence !== undefined ? confidence : "n/a"],
      ["Time range", timeRange || "n/a"],
    ].filter(([, v]) => v !== null && v !== undefined && v !== "");

    fields.forEach(([k, v]) => {
      const wrapper = document.createElement("div");
      appendText(wrapper, "span", `${k}:`, "trail-key");
      appendText(wrapper, "span", safeString(v), "trail-val");
      row.appendChild(wrapper);
    });

    container.prepend(row);
  }

  // Ingest video list and bootstrap selected console
  async function bootRetroConsole() {
    const payload = await apiGet("/api/system/videos");
    state.videos = Array.isArray(payload) ? payload : (payload.videos || []);

    renderVideoSelector();

    const select = document.getElementById("dataset-select");
    const activeId = select ? select.value : null;

    if (activeId) {
      await loadDataset(activeId);
    }
  }

  // Fetch and Load selected Video scenes
  async function loadDataset(videoId) {
    state.activeVideoId = videoId;
    state.searchResults = [];
    state.selectedSceneId = null;
    state.selectedEntity = null;
    state.videoMeta = null;
    state.intelFilter = null;   // clear any intel filter from previous dataset

    try {
      // Fire scenes + full timeline in parallel
      const [scenesPayload, timelinePayload] = await Promise.all([
        apiGet(`/api/videos/${encodeURIComponent(videoId)}/scenes`),
        apiGet(`/api/videos/${encodeURIComponent(videoId)}/timeline/full`).catch(() => null),
      ]);

      // Store video-level metadata rollup (Sprint 3)
      if (timelinePayload && typeof timelinePayload === "object" && timelinePayload.metadata) {
        state.videoMeta = {
          ...timelinePayload.metadata,
          // Hoist top-level TimelineResponse fields into videoMeta for convenience
          total_scenes: timelinePayload.total_scenes || null,
          total_segments: timelinePayload.total_segments || null,
        };
      }
      const scenesList = Array.isArray(scenesPayload) ? scenesPayload : (scenesPayload.scenes || []);

      // Adapt flat backend outputs to expected shapes (mapping transcripts/entities structure)
      state.scenes = scenesList.map((scene) => {
        const entities = Array.isArray(scene.entities) ? scene.entities : [];
        const normalizedEntities = entities.map((item) => {
          if (typeof item === "string") {
            return { name: item, type: "generic" };
          }
          return {
            // _list_dicts() wraps raw strings as {text:"..."} — handle all key variants
            name: item.label || item.name || item.text || "generic",
            type: item.entity_type || item.type || item.category || "generic",
          };
        });

        // Parse transcripts from temporal logs
        const dialogList = [];
        if (scene.transcript) {
          dialogList.push({
            speaker: scene.dominant_speaker_id || "Dialogue",
            text: scene.transcript,
            start: scene.start,
            end: scene.end,
          });
        }

        // Normalize detected objects — API returns either string[] or {label}[]
        const rawObjects = Array.isArray(scene.objects) ? scene.objects : [];
        const normalizedObjects = rawObjects.map((obj) =>
          typeof obj === "string" ? obj : (obj && (obj.label || obj.name)) || ""
        ).filter(Boolean);

        // Top audio emotion: always normalize to string | null
        const emotionRanking = Array.isArray(scene.audio_emotion_ranking) ? scene.audio_emotion_ranking : [];

        // Safely extract a label string from any ranking entry shape
        function extractEmotionLabel(entry) {
          if (!entry) return null;
          if (typeof entry === "string") return entry;
          // {label, score}, {name, score}, {emotion, ...} etc.
          return String(entry.label || entry.name || entry.emotion || entry.category || "") || null;
        }

        const topRankedLabel = emotionRanking.length > 0 ? extractEmotionLabel(emotionRanking[0]) : null;
        const rawTopEmotion = scene.audio_emotion_top_candidate || topRankedLabel || scene.audio_emotion;
        // Guarantee topEmotion is always string | null — never an object
        const topEmotion = rawTopEmotion && typeof rawTopEmotion === "string" ? rawTopEmotion
          : rawTopEmotion && typeof rawTopEmotion === "object" ? extractEmotionLabel(rawTopEmotion)
          : null;

        return {
          id: scene.scene_id ?? scene.id,
          start: scene.start,
          end: scene.end,
          summary: scene.summary ?? scene.visual_caption ?? "No description available.",
          keyframe_url: scene.representative_frame_endpoint ?? scene.representative_frame,
          entities: normalizedEntities,
          dialogue: dialogList,
          // Sprint 1 enrichment fields
          objects: normalizedObjects,
          visual_caption: scene.visual_caption || null,
          ocr_text: scene.ocr_text || null,
          tags: Array.isArray(scene.tags) ? scene.tags : [],
          sentiment_label: scene.sentiment_label || null,
          sentiment_score: typeof scene.sentiment_score === "number" ? scene.sentiment_score : null,
          audio_emotion: topEmotion,
          audio_emotion_ranking: emotionRanking,
          content_state: scene.content_state || "signal",
          // Sprint 2: entity channels
          scene_present_entities: normalizeEntityList(scene.scene_present_entities),
          dialogue_mentioned_entities: normalizeEntityList(scene.dialogue_mentioned_entities),
          candidate_visible_people: normalizeEntityList(scene.candidate_visible_people),
          // Sprint 2: scene context
          scene_context_llm: scene.scene_context_llm || null,
          scene_context_epistemic: scene.scene_context_epistemic || null,
          // P0 additions: text emotion + interaction fields
          text_emotion_ranking: Array.isArray(scene.text_emotion_ranking) ? scene.text_emotion_ranking : [],
          time_hints: scene.time_hints || null,
          interaction_dominance: scene.interaction_dominance || null,
          conversation_owner: scene.conversation_owner || null,
          speaker_aligned_mentions: Array.isArray(scene.speaker_aligned_mentions) ? scene.speaker_aligned_mentions : [],
          // Sprint 4 (P2) additions
          keywords: Array.isArray(scene.keywords) ? scene.keywords : [],
          ocr_date_candidates: Array.isArray(scene.ocr_date_candidates) ? scene.ocr_date_candidates : [],
          speaker_count: typeof scene.speaker_count === "number" ? scene.speaker_count : null,
          transcript_entity_disagreements: Array.isArray(scene.transcript_entity_disagreements) ? scene.transcript_entity_disagreements : [],
          scene_context_arbitration: scene.scene_context_arbitration || null,
        };
      });

      // Graph builder
      state.graph = buildEntityGraph(state.scenes);

      const canvas = document.getElementById("graph-canvas");
      if (canvas) {
        // Adjust canvas pixel dimensions to match client layout
        const rect = canvas.getBoundingClientRect();
        canvas.width = Math.floor(rect.width) || 600;
        canvas.height = Math.floor(rect.height) || 400;
        
        state.targetScale = 1.0;
        state.targetOffset = { x: 0, y: 0 };
        state.canvasScale = 1.0;
        state.canvasOffset = { x: 0, y: 0 };

        calculateLayout(state.graph);
      }

      renderTimelineGrid();
      drawGraph();
      renderInspector();
      renderEntityFilterChecklist(false);
      renderVideoIntelPanel();  // Sprint 3

      // Log initial boot event
      logDataTrail(
        "Load Dataset",
        "GET /api/videos/" + videoId + "/scenes",
        videoId,
        "scene database",
        "Bootstrapped dataset scenes successfully.",
        1.0,
        ""
      );
    } catch (err) {
      console.error("Failed to load dataset: ", err);
      logDataTrail("Error", "API fetch", videoId, "network", err.message, 0.0, "");
    }
  }

  // ─── Sprint 3+: Video Intelligence Panel (Interactive) ────────

  // Apply an intel-driven filter to the timeline (emotion / sentiment / tag)
  function setIntelFilter(type, value) {
    if (state.intelFilter && state.intelFilter.type === type && state.intelFilter.value === value) {
      state.intelFilter = null; // toggle off
    } else {
      state.intelFilter = { type, value };
    }
    renderVideoIntelPanel();
    renderTimelineGrid();
  }

  function clearIntelFilter() {
    state.intelFilter = null;
    renderVideoIntelPanel();
    renderTimelineGrid();
  }

  function scenePassesIntelFilter(scene) {
    const f = state.intelFilter;
    if (!f) return true;
    if (f.type === "emotion") {
      const audioMatch = scene.audio_emotion && scene.audio_emotion.toLowerCase() === f.value.toLowerCase();
      const textMatch = Array.isArray(scene.text_emotion_ranking) &&
        scene.text_emotion_ranking.some(e => (e.label || e || "").toLowerCase() === f.value.toLowerCase());
      return audioMatch || textMatch;
    }
    if (f.type === "sentiment") {
      return scene.sentiment_label && scene.sentiment_label.toLowerCase() === f.value.toLowerCase();
    }
    if (f.type === "tag") {
      const tagsArr = Array.isArray(scene.tags) ? scene.tags : [];
      const tagStr = tagsArr.map(t => (typeof t === "string" ? t : (t.label || t.name || "")).toLowerCase());
      const ctxTags = [];
      if (scene.scene_context_llm && typeof scene.scene_context_llm === "object") {
        ["primary_tags", "contextual_tags", "structural_tags"].forEach(k => {
          if (Array.isArray(scene.scene_context_llm[k]))
            ctxTags.push(...scene.scene_context_llm[k].map(t => t.toLowerCase()));
        });
      }
      const fv = f.value.toLowerCase();
      return tagStr.includes(fv) || ctxTags.includes(fv);
    }
    return true;
  }

  function renderVideoIntelPanel() {
    const meta = state.videoMeta;
    const activeFilter = state.intelFilter;

    // ── Active filter indicator pill ──────────────────────────────
    let filterBar = document.getElementById("intel-filter-bar");
    if (!filterBar) {
      filterBar = document.createElement("div");
      filterBar.id = "intel-filter-bar";
      filterBar.className = "intel-filter-bar";
      const panelEl = document.getElementById("video-intel-panel");
      if (panelEl) panelEl.insertBefore(filterBar, panelEl.firstChild);
    }
    if (activeFilter) {
      filterBar.hidden = false;
      filterBar.innerHTML = "";
      const pill = document.createElement("span");
      pill.className = "intel-active-filter-pill";
      pill.title = "Click to clear intel filter";
      pill.textContent = `◆ ${activeFilter.type}: "${activeFilter.value}"  ×`;
      pill.addEventListener("click", clearIntelFilter);
      filterBar.appendChild(pill);
    } else {
      filterBar.hidden = true;
    }

    // ── Emotion Arc ─────────────────────────────────────────────
    const audioEmEl = document.getElementById("intel-audio-emotions");
    if (audioEmEl) {
      audioEmEl.innerHTML = "";
      const audioRows = Array.isArray(meta && meta.top_audio_emotion_score_signals)
        ? meta.top_audio_emotion_score_signals : [];
      const textRows = Array.isArray(meta && meta.top_text_emotions)
        ? meta.top_text_emotions : [];

      if (!audioRows.length && !textRows.length) {
        audioEmEl.innerHTML = '<span class="intel-empty">No emotion data.</span>';
      } else {
        const merged = {};
        textRows.forEach(r => { if (r.emotion) merged[r.emotion] = { ...r, channel: "text" }; });
        audioRows.forEach(r => { if (r.emotion) merged[r.emotion] = { ...r, channel: "audio" }; });
        const rows = Object.values(merged).sort((a, b) => (b.count || 0) - (a.count || 0)).slice(0, 8);
        const maxCount = rows[0] ? (rows[0].count || 1) : 1;

        rows.forEach(row => {
          const isActive = activeFilter && activeFilter.type === "emotion"
            && activeFilter.value.toLowerCase() === row.emotion.toLowerCase();
          const bar = document.createElement("div");
          bar.className = `intel-bar-row intel-clickable${isActive ? " intel-filter-active" : ""}`;
          bar.title = `Filter timeline to "${row.emotion}" — click to toggle`;
          const pct = Math.round(((row.count || 0) / maxCount) * 100);
          const avgScore = typeof row.average_score === "number" ? (row.average_score * 100).toFixed(0) : null;
          const channelClass = row.channel === "audio" ? "audio" : "text";

          const labelEl = document.createElement("span");
          labelEl.className = `intel-bar-label ${channelClass}`;
          labelEl.textContent = row.emotion;
          const track = document.createElement("div");
          track.className = "intel-bar-track";
          const fill = document.createElement("div");
          fill.className = `intel-bar-fill ${channelClass}`;
          fill.style.width = `${pct}%`;
          track.appendChild(fill);
          const metaEl = document.createElement("span");
          metaEl.className = "intel-bar-meta";
          metaEl.innerHTML = `${row.count}×${avgScore ? ` <em>${avgScore}%</em>` : ""}`;

          bar.appendChild(labelEl);
          bar.appendChild(track);
          bar.appendChild(metaEl);
          bar.addEventListener("click", () => setIntelFilter("emotion", row.emotion));
          audioEmEl.appendChild(bar);
        });
      }
    }

    // ── Sentiment ───────────────────────────────────────────────
    const sentEl = document.getElementById("intel-sentiment");
    if (sentEl) {
      sentEl.innerHTML = "";
      const sentRows = Array.isArray(meta && meta.top_sentiment_labels) ? meta.top_sentiment_labels : [];
      if (!sentRows.length) {
        sentEl.innerHTML = '<span class="intel-empty">No sentiment data.</span>';
      } else {
        const total = sentRows.reduce((s, r) => s + (r.count || 0), 0) || 1;
        sentRows.forEach(row => {
          const pct = Math.round(((row.count || 0) / total) * 100);
          const sl = (row.label || "").toLowerCase();
          const isActive = activeFilter && activeFilter.type === "sentiment"
            && activeFilter.value.toLowerCase() === sl;
          const pill = document.createElement("span");
          pill.className = `intel-sentiment-pill intel-clickable ${sl === "positive" ? "pos" : sl === "negative" ? "neg" : "neu"}${isActive ? " intel-filter-active" : ""}`;
          pill.title = `Filter timeline to ${sl} scenes (${row.count} total) — click to toggle`;
          pill.textContent = `${sl} ${pct}%`;
          pill.addEventListener("click", () => setIntelFilter("sentiment", sl));
          sentEl.appendChild(pill);
        });
      }
    }

    // ── Most Discussed People ────────────────────────────────────
    const peopleEl = document.getElementById("intel-people");
    if (peopleEl) {
      peopleEl.innerHTML = "";
      const ownerRows = Array.isArray(meta && meta.top_conversation_owners) ? meta.top_conversation_owners : [];
      const mentionRows = Array.isArray(meta && meta.top_speaker_aligned_mentions) ? meta.top_speaker_aligned_mentions : [];

      const people = {};
      mentionRows.forEach(r => {
        const k = (r.entity || r.text || "").toLowerCase();
        if (!k) return;
        people[k] = { name: r.entity || r.text, mentions: r.count || 0, owned: 0 };
      });
      ownerRows.forEach(r => {
        const k = (r.entity || r.text || "").toLowerCase();
        if (!k) return;
        if (!people[k]) people[k] = { name: r.entity || r.text, mentions: 0, owned: 0 };
        people[k].owned = r.count || 0;
      });

      const sorted = Object.values(people)
        .sort((a, b) => (b.owned + b.mentions) - (a.owned + a.mentions))
        .slice(0, 8);

      if (!sorted.length) {
        peopleEl.innerHTML = '<span class="intel-empty">No people data.</span>';
      } else {
        const maxScore = Math.max(...sorted.map(p => p.owned + p.mentions), 1);
        sorted.forEach(person => {
          const total = person.owned + person.mentions;
          const pct = Math.round((total / maxScore) * 100);
          const row = document.createElement("div");
          row.className = "intel-person-row intel-clickable";
          row.title = `Select "${person.name}" in graph`;

          const nameEl = document.createElement("span");
          nameEl.className = "intel-person-name";
          nameEl.textContent = person.name;
          nameEl.title = `${person.owned} scene owner · ${person.mentions} mentions`;

          const track = document.createElement("div");
          track.className = "intel-bar-track";
          const fill = document.createElement("div");
          fill.className = "intel-bar-fill person";
          fill.style.width = `${pct}%`;
          track.appendChild(fill);

          const countEl = document.createElement("span");
          countEl.className = "intel-bar-meta";
          countEl.textContent = total;

          row.appendChild(nameEl);
          row.appendChild(track);
          row.appendChild(countEl);
          row.addEventListener("click", () => singleSelectEntity(normalizeEntityName(person.name)));
          peopleEl.appendChild(row);
        });
      }
    }

    // ── Context Tags Cloud ───────────────────────────────────────
    const tagsEl = document.getElementById("intel-tags");
    if (tagsEl) {
      tagsEl.innerHTML = "";
      const tagRows = Array.isArray(meta && meta.top_scene_context_tags) ? meta.top_scene_context_tags : [];
      if (!tagRows.length) {
        tagsEl.innerHTML = '<span class="intel-empty">No context tags.</span>';
      } else {
        const maxC = tagRows[0].count || 1;
        tagRows.slice(0, 20).forEach(row => {
          const weight = Math.max(0.55, (row.count || 1) / maxC);
          const isActive = activeFilter && activeFilter.type === "tag"
            && activeFilter.value.toLowerCase() === (row.tag || "").toLowerCase();
          const chip = document.createElement("span");
          chip.className = `intel-tag-chip intel-clickable${isActive ? " intel-filter-active" : ""}`;
          chip.textContent = row.tag;
          chip.title = `${row.count} scenes — click to filter timeline`;
          chip.style.opacity = isActive ? "1" : weight.toFixed(2);
          chip.style.fontSize = `${Math.round(9 + weight * 3)}px`;
          chip.addEventListener("click", () => setIntelFilter("tag", row.tag));
          tagsEl.appendChild(chip);
        });
      }
    }

    // ── Coverage Counters ────────────────────────────────────────
    const covEl = document.getElementById("intel-coverage");
    if (covEl) {
      covEl.innerHTML = "";
      const total = (meta && meta.total_scenes) || state.scenes.length;
      const fields = [
        ["scene_context_llm", "Context LLM"],
        ["audio_emotion_ranking", "Audio Emo"],
        ["text_emotion_ranking", "Text Emo"],
        ["sentiment", "Sentiment"],
        ["interaction_dominance", "Dominance"],
        ["conversation_owner", "Owner"],
        ["speaker_aligned_mentions", "Mentions"],
        ["candidate_visible_people", "Visual"],
        ["scene_context_epistemic", "Epistemic"],
        ["scene_context_arbitration", "Arbitration"],
        ["transcript_entity_disagreements", "Conflicts"],
      ];
      fields.forEach(([key, label]) => {
        const count = (meta && meta[`segments_with_${key}`]) || 0;
        const pct = total > 0 ? Math.round((count / total) * 100) : 0;
        const badge = document.createElement("div");
        badge.className = `intel-coverage-badge${pct >= 90 ? " full" : pct >= 50 ? " partial" : " low"}`;
        badge.title = `${count} of ${total} scenes`;
        const labelEl = document.createElement("span");
        labelEl.className = "cov-label";
        labelEl.textContent = label;
        const pctEl = document.createElement("span");
        pctEl.className = "cov-pct";
        pctEl.textContent = `${pct}%`;
        badge.appendChild(labelEl);
        badge.appendChild(pctEl);
        covEl.appendChild(badge);
      });
    }

    // ── Pipeline Health ──────────────────────────────────────────
    const healthEl = document.getElementById("intel-health");
    if (healthEl) {
      healthEl.innerHTML = "";
      if (!meta) { healthEl.innerHTML = '<span class="intel-empty">No health data.</span>'; return; }

      const p6ok = meta.phase6_complete === true;
      const p6hok = meta.phase6_harmonized === true;
      const policy = meta.audio_emotion_policy || null;
      const segs = meta.total_segments || null;
      const conflictCounts = Array.isArray(meta.transcript_entity_disagreement_category_counts)
        ? meta.transcript_entity_disagreement_category_counts : [];

      const statusRow = document.createElement("div");
      statusRow.className = "intel-health-row";
      [
        [p6ok, "Phase6", "Complete", "Incomplete"],
        [p6hok, "Harmonized", "Yes", "No"],
      ].forEach(([ok, labelText, yes, no]) => {
        const chip = document.createElement("span");
        chip.className = `intel-health-chip ${ok ? "ok" : "warn"}`;
        chip.textContent = `${labelText}: ${ok ? yes : no}`;
        statusRow.appendChild(chip);
      });
      if (segs !== null) {
        const segChip = document.createElement("span");
        segChip.className = "intel-health-chip neutral";
        segChip.textContent = `${segs} segs`;
        statusRow.appendChild(segChip);
      }
      if (policy) {
        const polChip = document.createElement("span");
        polChip.className = "intel-health-chip neutral";
        polChip.textContent = `policy: ${String(policy).replace(/_/g, " ")}`;
        polChip.title = `Audio emotion selection policy: ${policy}`;
        statusRow.appendChild(polChip);
      }
      healthEl.appendChild(statusRow);

      if (conflictCounts.length > 0) {
        const confRow = document.createElement("div");
        confRow.className = "intel-health-row";
        conflictCounts.slice(0, 4).forEach(item => {
          const chip = document.createElement("span");
          chip.className = "intel-health-chip conflict";
          const shortCat = (item.category || "")
            .replace(/transcript_|_entity|_name/g, "").replace(/_/g, " ");
          chip.textContent = `${shortCat}: ${item.count}`;
          chip.title = item.category || "";
          confRow.appendChild(chip);
        });
        healthEl.appendChild(confRow);
      }

      if (!p6ok && !p6hok && !segs && !policy && !conflictCounts.length) {
        healthEl.innerHTML = '<span class="intel-empty">No health data.</span>';
      }
    }
  }

  // ─── Handle Dynamic Resize of Canvas Layout ───────────────────
  function resizeCanvas() {
    const canvas = document.getElementById("graph-canvas");
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    if (canvas.width !== Math.floor(rect.width) || canvas.height !== Math.floor(rect.height)) {
      canvas.width = Math.floor(rect.width);
      canvas.height = Math.floor(rect.height);
      drawGraph();
    }
  }

  // Execute Multimodal Search Queries
  async function executeSearch() {
    const input = document.getElementById("query-input");
    const query = String(input ? input.value : "").trim();
    if (!query) return;

    state.lastQuery = query;
    state.searchActive = true;

    // Check if query matches any entity node (case-insensitive)
    const normalizedQuery = query.toLowerCase();
    const matchingNode = state.graph.nodes.find(
      (n) => n.label.toLowerCase() === normalizedQuery || n.id.toLowerCase() === normalizedQuery
    );

    if (matchingNode) {
      if (!state.selectedEntities.includes(matchingNode.id)) {
        state.selectedEntities.push(matchingNode.id);
      }
      state.selectedEntity = matchingNode.id;

      // Zoom and center graph canvas on matching node
      const canvas = document.getElementById("graph-canvas");
      if (canvas) {
        if (state.graphMode === "3D") {
          const alpha = -Math.atan2(matchingNode.base3dX || 0, matchingNode.base3dZ || 0);
          const beta = -Math.atan2(matchingNode.base3dY || 0, Math.hypot(matchingNode.base3dX || 0, matchingNode.base3dZ || 0));

          state.targetRotation = { alpha, beta };
          state.graphSpinSpeed = { alpha: 0, beta: 0 };
          state.isAutoRotating = true;

          const projected = rotate3d(matchingNode.base3dX || 0, matchingNode.base3dY || 0, matchingNode.base3dZ || 0, alpha, beta);
          state.targetScale = 1.8;
          state.targetOffset.x = -projected.x * 1.8;
          state.targetOffset.y = -projected.y * 1.8;
        } else {
          state.targetScale = 1.8;
          state.targetOffset.x = -matchingNode.x * 1.8;
          state.targetOffset.y = -matchingNode.y * 1.8;
        }
        triggerGraphAnimation();
      }
      renderEntityFilterChecklist(false);
    }

    logDataTrail(
      query,
      "POST /api/search/multimodal",
      state.activeVideoId,
      "user search input",
      `Executing multimodal query: "${query}"`,
      1.0,
      ""
    );

    try {
      // Modality selection mapping
      const modesList = Array.from(state.modes);
      const searchResponse = await apiPost("/api/search/multimodal", {
        query,
        modalities: modesList,
        top_k: 50,
      });

      // Filter grid highlighted matching scenes for active video (robust mapping check)
      const allResults = searchResponse.results || [];
      state.searchResults = allResults.filter(
        (res) => res.timeline_video_id === state.activeVideoId || res.video_id === state.activeVideoId
      );
      renderTimelineGrid();

      // Log matching results data trail details
      if (state.searchResults.length) {
        state.searchResults.forEach((res, i) => {
          const matchedScene = state.scenes.find((s) => s.id === res.scene_id);
          const timeRangeStr = matchedScene ? `${formatTime(matchedScene.start)} - ${formatTime(matchedScene.end)}` : "";
          
          // Map evidence source to nice labels
          const evidenceSource = (res.matched_modes || ["text"])
            .map(m => m === "text" ? "transcript" : m === "visual" ? "keyframe" : m)
            .join(", ");

          logDataTrail(
            query,
            "POST /api/search/multimodal",
            state.activeVideoId,
            evidenceSource,
            `Match result #${i + 1}: ${res.reason || "Matched semantic query keywords."}`,
            res.score,
            timeRangeStr
          );
        });
      } else {
        logDataTrail(query, "POST /api/search/multimodal", state.activeVideoId, "search response", "No results found for active dataset.", 0.0, "");
      }
    } catch (err) {
      console.error("Search failed: ", err);
      logDataTrail(query, "POST /api/search/multimodal", state.activeVideoId, "network error", err.message, 0.0, "");
    }
  }

  // Accessibility Controls & Event Listeners
  function initAccessibility() {
    const screen = document.getElementById("crt-screen");
    const toggleScanlines = document.getElementById("toggle-scanlines");
    const toggleEffects = document.getElementById("toggle-effects");
    const toggleIntel = document.getElementById("toggle-intel-btn");
    const intelPanel = document.getElementById("video-intel-panel");

    if (!screen || !toggleScanlines || !toggleEffects) return;

    // Intel panel toggle
    if (toggleIntel && intelPanel) {
      toggleIntel.addEventListener("click", () => {
        state.intelVisible = !state.intelVisible;
        intelPanel.hidden = !state.intelVisible;
        
        const resizerIntel = document.getElementById("resizer-intel");
        if (resizerIntel) resizerIntel.hidden = !state.intelVisible;

        toggleIntel.textContent = state.intelVisible ? "Intel: ON" : "Intel: OFF";
        toggleIntel.classList.toggle("intel-active", state.intelVisible);
        if (state.intelVisible && state.videoMeta) renderVideoIntelPanel();
      });
    }

    toggleScanlines.addEventListener("click", () => {
      const active = screen.classList.toggle("no-scanlines");
      toggleScanlines.textContent = active ? "Scanlines: OFF" : "Scanlines: ON";
      toggleScanlines.classList.toggle("btn-disabled", active);
    });

    toggleEffects.addEventListener("click", () => {
      const active = screen.classList.toggle("no-effects");
      toggleEffects.textContent = active ? "Effects: OFF" : "Effects: ON";
      toggleEffects.classList.toggle("btn-disabled", active);
      drawGraph(); // Redraw canvas graph to clear glows
    });
  }

  // Layout Management (Resizing, Collapsing, Reopening sidebars and panels)
  function initLayoutControls() {
    const layoutState = {
      leftWidth: 320,
      rightWidth: 380,
      bottomHeight: 280,
      headerHeight: 48,
      leftCollapsed: false,
      rightCollapsed: false,
      bottomCollapsed: false,
      headerCollapsed: false,
      lastLeftWidth: 320,
      lastRightWidth: 380,
      lastBottomHeight: 280,
      lastHeaderHeight: 48
    };

    const grid = document.querySelector(".grid-layout");
    const screen = document.getElementById("crt-screen");
    const searchPanel = document.querySelector(".search-panel");
    const inspectorPanel = document.querySelector(".inspector-panel");
    const timelinePanel = document.querySelector(".timeline-panel");
    const appHeader = document.querySelector(".app-header");
    
    const resizerLeft = document.getElementById("resizer-left");
    const resizerRight = document.getElementById("resizer-right");
    const resizerBottom = document.getElementById("resizer-bottom");

    const collapseLeft = document.getElementById("collapse-left-btn");
    const collapseRight = document.getElementById("collapse-right-btn");
    const collapseBottom = document.getElementById("collapse-bottom-btn");
    const collapseTop = document.getElementById("collapse-top-btn");

    const restoreLeft = document.getElementById("restore-left-btn");
    const restoreRight = document.getElementById("restore-right-btn");
    const restoreBottom = document.getElementById("restore-bottom-btn");
    const restoreTop = document.getElementById("restore-top-btn");

    function applyLayout() {
      if (!grid || !screen) return;

      // Left Panel
      if (layoutState.leftCollapsed) {
        grid.style.setProperty("--left-width", "0px");
        grid.style.setProperty("--left-resizer-width", "0px");
        if (searchPanel) searchPanel.style.display = "none";
        if (resizerLeft) resizerLeft.style.display = "none";
        if (restoreLeft) restoreLeft.hidden = false;
      } else {
        grid.style.setProperty("--left-width", `${layoutState.leftWidth}px`);
        grid.style.setProperty("--left-resizer-width", "10px");
        if (searchPanel) searchPanel.style.display = "";
        if (resizerLeft) resizerLeft.style.display = "";
        if (restoreLeft) restoreLeft.hidden = true;
      }

      // Right Panel
      if (layoutState.rightCollapsed) {
        grid.style.setProperty("--right-width", "0px");
        grid.style.setProperty("--right-resizer-width", "0px");
        if (inspectorPanel) inspectorPanel.style.display = "none";
        if (resizerRight) resizerRight.style.display = "none";
        if (restoreRight) restoreRight.hidden = false;
      } else {
        grid.style.setProperty("--right-width", `${layoutState.rightWidth}px`);
        grid.style.setProperty("--right-resizer-width", "10px");
        if (inspectorPanel) inspectorPanel.style.display = "";
        if (resizerRight) resizerRight.style.display = "";
        if (restoreRight) restoreRight.hidden = true;
      }

      // Bottom Panel
      if (layoutState.bottomCollapsed) {
        grid.style.setProperty("--bottom-height", "0px");
        grid.style.setProperty("--bottom-resizer-height", "0px");
        if (timelinePanel) timelinePanel.style.display = "none";
        if (resizerBottom) resizerBottom.style.display = "none";
        if (restoreBottom) restoreBottom.hidden = false;
      } else {
        grid.style.setProperty("--bottom-height", `${layoutState.bottomHeight}px`);
        grid.style.setProperty("--bottom-resizer-height", "10px");
        if (timelinePanel) timelinePanel.style.display = "";
        if (resizerBottom) resizerBottom.style.display = "";
        if (restoreBottom) restoreBottom.hidden = true;
      }

      // Top Header
      if (layoutState.headerCollapsed) {
        if (appHeader) appHeader.classList.add("collapsed");
        if (restoreTop) restoreTop.hidden = false;
      } else {
        if (appHeader) appHeader.classList.remove("collapsed");
        if (restoreTop) restoreTop.hidden = true;
      }

      resizeCanvas();
    }

    // Collapse event listeners
    if (collapseLeft) {
      collapseLeft.addEventListener("click", () => {
        layoutState.lastLeftWidth = layoutState.leftWidth;
        layoutState.leftCollapsed = true;
        applyLayout();
      });
    }
    if (restoreLeft) {
      restoreLeft.addEventListener("click", () => {
        layoutState.leftWidth = layoutState.lastLeftWidth;
        layoutState.leftCollapsed = false;
        applyLayout();
      });
    }

    if (collapseRight) {
      collapseRight.addEventListener("click", () => {
        layoutState.lastRightWidth = layoutState.rightWidth;
        layoutState.rightCollapsed = true;
        applyLayout();
      });
    }
    if (restoreRight) {
      restoreRight.addEventListener("click", () => {
        layoutState.rightWidth = layoutState.lastRightWidth;
        layoutState.rightCollapsed = false;
        applyLayout();
      });
    }

    if (collapseBottom) {
      collapseBottom.addEventListener("click", () => {
        layoutState.lastBottomHeight = layoutState.bottomHeight;
        layoutState.bottomCollapsed = true;
        applyLayout();
      });
    }
    if (restoreBottom) {
      restoreBottom.addEventListener("click", () => {
        layoutState.bottomHeight = layoutState.lastBottomHeight;
        layoutState.bottomCollapsed = false;
        applyLayout();
      });
    }

    if (collapseTop) {
      collapseTop.addEventListener("click", () => {
        layoutState.lastHeaderHeight = layoutState.headerHeight;
        layoutState.headerCollapsed = true;
        applyLayout();
      });
    }
    if (restoreTop) {
      restoreTop.addEventListener("click", () => {
        layoutState.headerHeight = layoutState.lastHeaderHeight;
        layoutState.headerCollapsed = false;
        applyLayout();
      });
    }

    // Drag Resizing Logic
    if (resizerLeft) {
      resizerLeft.addEventListener("mousedown", (e) => {
        e.preventDefault();
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";

        const gridRect = grid.getBoundingClientRect();

        function onMouseMove(moveEvent) {
          let width = moveEvent.clientX - gridRect.left;
          if (width < 120) {
            layoutState.lastLeftWidth = 280;
            layoutState.leftCollapsed = true;
            stopResizing();
            applyLayout();
          } else {
            width = Math.max(150, Math.min(width, gridRect.width * 0.45));
            layoutState.leftWidth = width;
            grid.style.setProperty("--left-width", `${width}px`);
            resizeCanvas();
          }
        }

        function stopResizing() {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", stopResizing);
          document.body.style.cursor = "";
          document.body.style.userSelect = "";
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", stopResizing);
      });
    }

    if (resizerRight) {
      resizerRight.addEventListener("mousedown", (e) => {
        e.preventDefault();
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";

        const gridRect = grid.getBoundingClientRect();

        function onMouseMove(moveEvent) {
          let width = gridRect.right - moveEvent.clientX;
          if (width < 120) {
            layoutState.lastRightWidth = 320;
            layoutState.rightCollapsed = true;
            stopResizing();
            applyLayout();
          } else {
            width = Math.max(150, Math.min(width, gridRect.width * 0.45));
            layoutState.rightWidth = width;
            grid.style.setProperty("--right-width", `${width}px`);
            resizeCanvas();
          }
        }

        function stopResizing() {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", stopResizing);
          document.body.style.cursor = "";
          document.body.style.userSelect = "";
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", stopResizing);
      });
    }

    if (resizerBottom) {
      resizerBottom.addEventListener("mousedown", (e) => {
        e.preventDefault();
        document.body.style.cursor = "row-resize";
        document.body.style.userSelect = "none";

        const gridRect = grid.getBoundingClientRect();

        function onMouseMove(moveEvent) {
          let height = gridRect.bottom - moveEvent.clientY;
          if (height < 70) {
            layoutState.lastBottomHeight = 220;
            layoutState.bottomCollapsed = true;
            stopResizing();
            applyLayout();
          } else {
            height = Math.max(100, Math.min(height, gridRect.height * 0.5));
            layoutState.bottomHeight = height;
            grid.style.setProperty("--bottom-height", `${height}px`);
            resizeCanvas();
          }
        }

        function stopResizing() {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", stopResizing);
          document.body.style.cursor = "";
          document.body.style.userSelect = "";
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", stopResizing);
      });
    }

    // Drag Resizing Logic for Top Video Intelligence Panel
    const resizerIntel = document.getElementById("resizer-intel");
    const intelPanel = document.getElementById("video-intel-panel");
    if (resizerIntel && intelPanel) {
      resizerIntel.addEventListener("mousedown", (e) => {
        e.preventDefault();
        document.body.style.cursor = "row-resize";
        document.body.style.userSelect = "none";

        const startHeight = intelPanel.offsetHeight;
        const startY = e.clientY;

        function onMouseMove(moveEvent) {
          const deltaY = moveEvent.clientY - startY;
          let newHeight = startHeight + deltaY;
          
          // Bound height between 80px and 450px
          newHeight = Math.max(80, Math.min(newHeight, 450));
          
          intelPanel.style.height = `${newHeight}px`;
          resizeCanvas(); // Trigger canvas redraw
        }

        function stopResizing() {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", stopResizing);
          document.body.style.cursor = "";
          document.body.style.userSelect = "";
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", stopResizing);
      });
    }

    // Collapsible Data Trail Logs Subsection Toggle
    const toggleDataTrailBtn = document.getElementById("toggle-data-trail-btn");
    const dataTrailSection = document.getElementById("data-trail-section");
    const inspectorDetails = document.getElementById("inspector-details");
    if (toggleDataTrailBtn && dataTrailSection) {
      toggleDataTrailBtn.addEventListener("click", () => {
        const isCollapsed = dataTrailSection.classList.toggle("collapsed");
        const subResizer = document.getElementById("resizer-subsection");
        if (subResizer) {
          subResizer.style.display = isCollapsed ? "none" : "";
        }
        // When collapsed, let details fill remaining space
        if (inspectorDetails) {
          inspectorDetails.style.flex = isCollapsed ? "1 1 auto" : "";
        }
      });
    }

    // Drag Resizing for Detail Inspector Subsection Splitter (VS Code style)
    const resizerSubsection = document.getElementById("resizer-subsection");
    const inspectorContent = document.querySelector(".inspector-content");

    if (resizerSubsection && inspectorContent && dataTrailSection) {
      resizerSubsection.addEventListener("mousedown", (e) => {
        e.preventDefault();
        if (dataTrailSection.classList.contains("collapsed")) return;

        document.body.style.cursor = "row-resize";
        document.body.style.userSelect = "none";

        const contentRect = inspectorContent.getBoundingClientRect();

        function onMouseMove(moveEvent) {
          let height = contentRect.bottom - moveEvent.clientY;
          height = Math.max(50, Math.min(height, contentRect.height * 0.65));
          // Set the CSS variable on the data-trail-section itself for correct flex sizing
          dataTrailSection.style.setProperty("--logs-height", `${height}px`);
          dataTrailSection.style.flex = `0 0 ${height}px`;
        }

        function stopResizing() {
          document.removeEventListener("mousemove", onMouseMove);
          document.removeEventListener("mouseup", stopResizing);
          document.body.style.cursor = "";
          document.body.style.userSelect = "";
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", stopResizing);
      });
    }
  }

  // Interactive Graph Controls (Drag / Scroll offsets / Zoom Flight)
  function initCanvasControls() {
    const canvas = document.getElementById("graph-canvas");
    if (!canvas) return;

    let dragMoveOffset = 0;

    canvas.addEventListener("mousedown", (e) => {
      dragMoveOffset = 0;
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      // Find node under current scale/offset
      const hit = state.graph.nodes.find((node) => {
        let nx, ny;
        if (state.graphMode === "3D") {
          if ((node.rotatedZ || 0) < 0) return false; // Only front-facing nodes in 3D
          nx = (node.rotatedX || 0) * state.canvasScale;
          ny = (node.rotatedY || 0) * state.canvasScale;
        } else {
          nx = node.x * state.canvasScale;
          ny = node.y * state.canvasScale;
        }
        const nodeScreenX = canvas.width / 2 + state.canvasOffset.x + nx;
        const nodeScreenY = canvas.height / 2 + state.canvasOffset.y + ny;
        const dist = Math.hypot(nodeScreenX - mouseX, nodeScreenY - mouseY);
        
        let depthScale = 1.0;
        if (state.graphMode === "3D") {
          depthScale = 0.5 + 0.65 * (((node.rotatedZ || 0) + 140) / 280);
        }
        const radius = (6 + Math.min(12, node.count * 1.5)) * depthScale;
        return dist <= radius + 6;
      });

      if (hit) {
        // Mark intent — selection happens on mouseup only if we didn't drag
        state.activeNode = hit;
        canvas.style.cursor = "grab";

        // In 3D mode, dragging a node starts a globe rotation drag instead of moving the node
        if (state.graphMode === "3D") {
          state.isDragging = true;
          state.dragStart = { x: e.clientX - state.canvasOffset.x, y: e.clientY - state.canvasOffset.y };
          canvas.style.cursor = "grabbing";
        }
      } else {
        // Start canvas pan / globe rotation
        state.isDragging = true;
        state.dragStart = { x: e.clientX - state.canvasOffset.x, y: e.clientY - state.canvasOffset.y };
        canvas.style.cursor = "grabbing";
      }
    });

    canvas.addEventListener("mousemove", (e) => {
      dragMoveOffset += Math.hypot(e.movementX, e.movementY);

      if (state.activeNode && state.graphMode !== "3D") {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        if (dragMoveOffset > 4) {
          // Drag node to reposition it
          state.activeNode.x = (mouseX - canvas.width / 2 - state.canvasOffset.x) / state.canvasScale;
          state.activeNode.y = (mouseY - canvas.height / 2 - state.canvasOffset.y) / state.canvasScale;
          drawGraph();
        }
      } else if (state.isDragging) {
        if (state.graphMode === "3D") {
          // Cancel auto-rotation on manual drag
          state.isAutoRotating = false;

          // Convert mouse movement to 3D rotation angles
          const dx = e.movementX * 0.007;
          const dy = e.movementY * 0.007;

          state.graphRotation.alpha += dx;
          state.graphRotation.beta += dy;

          // Capture momentum for continuous spin
          state.graphSpinSpeed.alpha = dx;
          state.graphSpinSpeed.beta = dy;
          state.isSpinning = true;

          drawGraph();
        } else {
          state.canvasOffset.x = e.clientX - state.dragStart.x;
          state.canvasOffset.y = e.clientY - state.dragStart.y;
          state.targetOffset.x = state.canvasOffset.x;
          state.targetOffset.y = state.canvasOffset.y;
          drawGraph();
        }
      }
    });

    canvas.addEventListener("mouseup", (e) => {
      canvas.style.cursor = "";
      const wasDrag = dragMoveOffset > 4;

      if (state.activeNode && !wasDrag) {
        // Clean click on a node: select it
        const hit = state.activeNode;
        if (e.ctrlKey || e.shiftKey) {
          toggleSelectEntity(hit.id);
        } else {
          singleSelectEntity(hit.id);
        }
      } else if (!state.activeNode && !state.isDragging && !wasDrag) {
        // Intentional click on empty canvas space — deselect entity filter
        if (state.selectedEntities.length > 0) {
          resetEntityFilters();
        }
      }

      state.isDragging = false;
      state.activeNode = null;
    });

    canvas.addEventListener("mouseleave", () => {
      state.isDragging = false;
      state.activeNode = null;
    });

    canvas.addEventListener("dblclick", (e) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      // Find node under current scale/offset
      const hit = state.graph.nodes.find((node) => {
        let nx, ny;
        if (state.graphMode === "3D") {
          if ((node.rotatedZ || 0) < 0) return false;
          nx = (node.rotatedX || 0) * state.canvasScale;
          ny = (node.rotatedY || 0) * state.canvasScale;
        } else {
          nx = node.x * state.canvasScale;
          ny = node.y * state.canvasScale;
        }
        const nodeScreenX = canvas.width / 2 + state.canvasOffset.x + nx;
        const nodeScreenY = canvas.height / 2 + state.canvasOffset.y + ny;
        const dist = Math.hypot(nodeScreenX - mouseX, nodeScreenY - mouseY);
        
        let depthScale = 1.0;
        if (state.graphMode === "3D") {
          depthScale = 0.5 + 0.65 * (((node.rotatedZ || 0) + 140) / 280);
        }
        const radius = (6 + Math.min(12, node.count * 1.5)) * depthScale;
        return dist <= radius + 6;
      });

      if (hit) {
        deselectEntity(hit.id);
      }
    });

    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomFactor = 1.15;
      let nextScale = state.targetScale;
      if (e.deltaY < 0) {
        nextScale = state.targetScale * zoomFactor;
      } else {
        nextScale = state.targetScale / zoomFactor;
      }

      // Bound scale between 0.3 and 5.0
      nextScale = Math.max(0.3, Math.min(5.0, nextScale));

      const relX = mouseX - canvas.width / 2;
      const relY = mouseY - canvas.height / 2;
      state.targetOffset.x = relX - (relX - state.targetOffset.x) * (nextScale / state.targetScale);
      state.targetOffset.y = relY - (relY - state.targetOffset.y) * (nextScale / state.targetScale);
      state.targetScale = nextScale;

      triggerGraphAnimation();
    }, { passive: false });

    const resetBtn = document.getElementById("reset-graph-btn");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        resetAllFilters(); // Full reset (search + entities) on explicit Reset View
      });
    }

    const toggle2dBtn = document.getElementById("toggle-graph-2d-btn");
    const toggle3dBtn = document.getElementById("toggle-graph-3d-btn");

    if (toggle2dBtn && toggle3dBtn) {
      toggle2dBtn.addEventListener("click", () => {
        if (state.graphMode === "2D") return;
        state.graphMode = "2D";
        toggle2dBtn.classList.add("active");
        toggle3dBtn.classList.remove("active");

        // Reset scale and offset to center
        state.targetScale = 1.0;
        state.targetOffset = { x: 0, y: 0 };
        triggerGraphAnimation();
      });

      toggle3dBtn.addEventListener("click", () => {
        if (state.graphMode === "3D") return;
        state.graphMode = "3D";
        toggle3dBtn.classList.add("active");
        toggle2dBtn.classList.remove("active");

        // Reset scale and offset, preserve 3D rotations
        state.targetScale = 1.0;
        state.targetOffset = { x: 0, y: 0 };
        triggerGraphAnimation();
      });
    }
  }

  // ─── Status Polling Loop & Ingestion Progress ─────────
  let wasIngesting = false;
  let ingestionStartTime = null;
  let pollingIntervalId = null;

  function startStatusPolling() {
    // Poll immediately, then every 3 seconds
    pollStatus();
    pollingIntervalId = setInterval(pollStatus, 3000);
  }

  async function pollStatus() {
    try {
      const statusPayload = await apiGet("/api/status");
      const processing = statusPayload.processing || {};
      const cliProgress = processing.cli_progress || {};
      const isActive = cliProgress.active === true;

      const progressWidget = document.getElementById("ingestion-progress-widget");
      const headerStatus = document.querySelector(".header-status");

      if (isActive) {
        if (!wasIngesting) {
          wasIngesting = true;
          ingestionStartTime = Date.now();
          if (progressWidget) progressWidget.hidden = false;
          if (headerStatus) {
            headerStatus.classList.add("ingesting");
          }
        }

        const pct = cliProgress.progress_percent !== undefined ? cliProgress.progress_percent : (processing.progress_percent || 0);
        const currentFile = cliProgress.current_video || processing.current_video || "02. 1988 - 1989.mp4";
        const currentStep = cliProgress.current_step || "processing";
        const stage = cliProgress.stage || "ingestion";
        const sceneIndex = cliProgress.scene_index || 0;
        const scenesTotal = cliProgress.scenes_total || "?";

        // Update widget UI
        const fileEl = document.getElementById("progress-file");
        if (fileEl) fileEl.textContent = `File: ${currentFile}`;

        const stepEl = document.getElementById("progress-step");
        if (stepEl) stepEl.textContent = `Step: ${currentStep}`;

        const barFill = document.getElementById("progress-bar-fill");
        if (barFill) barFill.style.width = `${pct}%`;

        const textEl = document.getElementById("progress-text");
        if (textEl) textEl.textContent = `${pct}%`;

        const stageEl = document.getElementById("progress-stage");
        if (stageEl) stageEl.textContent = `Stage: ${stage}`;

        const sceneEl = document.getElementById("progress-scene-count");
        if (sceneEl) sceneEl.textContent = `Scene: ${sceneIndex} of ${scenesTotal}`;

        const elapsedSec = Math.floor((Date.now() - ingestionStartTime) / 1000);
        const elapsedEl = document.getElementById("progress-elapsed");
        if (elapsedEl) elapsedEl.textContent = `Elapsed: ${elapsedSec}s`;

        if (headerStatus) {
          headerStatus.textContent = `Status: INGESTING (${pct}%)`;
        }
      } else {
        if (wasIngesting) {
          // Transitioning from active to idle: Show 100% completed
          wasIngesting = false;
          
          const barFill = document.getElementById("progress-bar-fill");
          if (barFill) barFill.style.width = "100%";

          const textEl = document.getElementById("progress-text");
          if (textEl) textEl.textContent = "100%";

          const stepEl = document.getElementById("progress-step");
          if (stepEl) stepEl.textContent = "Step: COMPLETED";

          const stageEl = document.getElementById("progress-stage");
          if (stageEl) stageEl.textContent = "Stage: finished";

          if (headerStatus) {
            headerStatus.textContent = "Status: ONLINE";
          }

          // Wait 3 seconds then hide and reload dataset
          setTimeout(async () => {
            if (progressWidget) progressWidget.hidden = true;
            if (headerStatus) {
              headerStatus.classList.remove("ingesting");
              headerStatus.textContent = "Status: ONLINE";
            }
            // Trigger boot loader to refresh dropdown and grid
            await bootRetroConsole();
          }, 3000);
        } else {
          // Normal idle state, make sure widget is hidden and status is normal
          if (progressWidget && !progressWidget.hidden) {
            progressWidget.hidden = true;
          }
          if (headerStatus && headerStatus.classList.contains("ingesting")) {
            headerStatus.classList.remove("ingesting");
            headerStatus.textContent = "Status: ONLINE";
          }
        }
      }
    } catch (err) {
      console.warn("Status polling error: ", err);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bootRetroConsole()
      .then(() => {
        initAccessibility();
        initLayoutControls();
        initCanvasControls();
        initTTS();
        startStatusPolling();

        // Canvas resize observer for responsive scaling without stretching
        const canvas = document.getElementById("graph-canvas");
        if (canvas) {
          const wrapper = canvas.parentElement;
          if (wrapper) {
            const resizeObserver = new ResizeObserver((entries) => {
              for (let entry of entries) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0) {
                  canvas.width = Math.floor(width);
                  canvas.height = Math.floor(height);
                  drawGraph();
                }
              }
            });
            resizeObserver.observe(wrapper);
          }
        }

        // Canvas resize handlers fallback
        window.addEventListener("resize", resizeCanvas);
        // Initial resize sync
        resizeCanvas();

        // Dataset dropdown change trigger
        const select = document.getElementById("dataset-select");
        if (select) {
          select.addEventListener("change", (e) => {
            if (e.target.value) {
              loadDataset(e.target.value);
            }
          });
        }

        // Search Form Submission
        const form = document.getElementById("search-form");
        if (form) {
          form.addEventListener("submit", (e) => {
            e.preventDefault();
            executeSearch();
          });
        }

        // Modality Mode selector buttons mapping
        const modeButtons = document.querySelectorAll(".mode-btn");
        modeButtons.forEach((btn) => {
          btn.addEventListener("click", () => {
            const currentMode = btn.getAttribute("data-mode");
            
            if (currentMode === "all") {
              const allActive = btn.classList.contains("active");
              modeButtons.forEach((b) => b.classList.toggle("active", !allActive));
              state.modes = !allActive ? new Set(["text", "visual", "audio"]) : new Set();
            } else {
              const active = btn.classList.toggle("active");
              if (active) {
                state.modes.add(currentMode);
              } else {
                state.modes.delete(currentMode);
              }
              // Adjust All button state depending on individual mode status
              const allBtn = document.querySelector('.mode-btn[data-mode="all"]');
              if (allBtn) {
                allBtn.classList.toggle("active", state.modes.size === 3);
              }
            }
          });
        });
      })
      .catch((err) => {
        console.error("Bootloader failed: ", err);
      });
  });
})();
