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
    datasetGeneration: 0,
    searchGeneration: 0,
    selectedSceneId: null,
    selectedOriginalMedia: null,
    activeInspectorTab: "overview",
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
    droppadVisible: false, // Sprint 4: Drop pad panel open state
    intelFilter: null,     // Sprint 3+: {type, value} filter from intel panel
    graphMode: "2D",       // "2D" or "3D"
    graphRotation: { alpha: 0.2, beta: 0.15 },
    graphSpinSpeed: { alpha: 0.0025, beta: 0.0008 },
    targetRotation: { alpha: 0.2, beta: 0.15 },
    isSpinning: true,
    isAutoRotating: false,
    activeSearchTab: "multimodal",
    activeTemporalSummaryJobId: null,
    temporalSummaryGeneration: 0,
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

  const originalAudio = {
    element: null,
    generation: 0,
  };

  const originalVideo = {
    element: null,
    generation: 0,
    desktop: null,
  };

  function pauseOriginalVideo() {
    if (originalVideo.element) originalVideo.element.pause();
    if (originalVideo.desktop) originalVideo.desktop.done();
  }

  function resetOriginalVideo() {
    if (originalVideo.desktop) originalVideo.desktop.done();
    originalVideo.desktop = null;
    originalVideo.generation += 1;
    const video = originalVideo.element;
    originalVideo.element = null;
    if (video) {
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
    const panel = document.getElementById("inspector-original-video");
    if (panel) {
      panel.innerHTML = "";
      panel.hidden = true;
    }
    const keyframe = document.getElementById("inspector-keyframe-zone");
    if (keyframe) keyframe.hidden = false;
  }

  async function desktopPlayerCommand(action, body, librarySource) {
    const path = `/api/media/desktop-player/${action}`;
    const url = typeof window !== "undefined" && window.GoodQLibrary ? window.GoodQLibrary.url(path, librarySource) : path;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(typeof result.detail === "string" ? result.detail : `Desktop playback failed (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return result;
  }

  function desktopPlayerWindow(element) {
    const rect = element.getBoundingClientRect();
    const bounded = (value, minimum, maximum) => Number.isFinite(value)
      ? Math.round(Math.max(minimum, Math.min(maximum, value))) : minimum;
    const width = bounded(rect.width, 240, 1920);
    const height = bounded(rect.height, 180, 1440);
    const screen = window.screen || {};
    const left = Number.isFinite(screen.availLeft) ? screen.availLeft : -32768;
    const top = Number.isFinite(screen.availTop) ? screen.availTop : -32768;
    const right = Number.isFinite(screen.availWidth) ? left + screen.availWidth - width : 32768;
    const bottom = Number.isFinite(screen.availHeight) ? top + screen.availHeight - height : 32768;
    return {
      x: bounded(window.screenX + rect.x, Math.max(-32768, left), Math.min(32768, Math.max(left, right))),
      y: bounded(window.screenY + Math.max(0, window.outerHeight - window.innerHeight) + rect.y,
        Math.max(-32768, top), Math.min(32768, Math.max(top, bottom))),
      width, height,
    };
  }

  function renderOriginalVideo(scene) {
    const librarySource = typeof window !== "undefined" ? window.GoodQLibrary?.source : undefined;
    if (scene.source_kind && scene.source_kind !== "video") {
      renderStandaloneSource(scene);
      return;
    }
    const panel = document.getElementById("inspector-original-video");
    if (!panel) return;
    panel.hidden = false;
    appendText(panel, "h3", "Original source video");
    const status = document.createElement("p");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const endpoint = scene.original_video_endpoint;
    const start = scene.start;
    if (scene.original_video_available !== true || typeof endpoint !== "string"
      || !/^\/api\/media\/video\/[^/?#]+\/source$/.test(endpoint)) {
      status.textContent = "Original source video unavailable.";
      panel.appendChild(status);
      return;
    }
    if (typeof start !== "number" || !Number.isFinite(start) || start < 0) {
      status.textContent = "Original source video unavailable: invalid scene start time.";
      panel.appendChild(status);
      return;
    }

    const video = document.createElement("video");
    video.controls = true;
    video.preload = "metadata";
    video.playsInline = true;
    video.hidden = true;
    video.setAttribute("aria-label", "Original source video");
    const keyframe = document.getElementById("inspector-keyframe-zone");
    const generation = originalVideo.generation;
    originalVideo.element = video;
    const isCurrent = () => originalVideo.element === video && originalVideo.generation === generation;
    const sourceMatch = endpoint.match(/^\/api\/media\/video\/([^/?#]+)\/source$/);
    const sceneId = scene.scene_id ?? scene.id;
    const playButton = document.createElement("button");
    playButton.type = "button";
    playButton.className = "original-video-play";
    playButton.textContent = "Play original video";
    const doneButton = document.createElement("button");
    doneButton.type = "button";
    doneButton.className = "original-video-done";
    doneButton.textContent = "Done with pop-out";
    doneButton.hidden = true;
    let failed = false;
    let initialSeek = false;
    let unsupported = false;
    let playIntent = false;
    let fallbackRequested = false;
    let playbackId = null;
    let pendingLaunch = null;
    let desktopGeneration = 0;
    let desktopTimer = null;
    let desktopAvailable = null;
    const clearPoll = () => {
      if (desktopTimer !== null) clearTimeout(desktopTimer);
      desktopTimer = null;
    };
    const release = async (token, releaseGeneration = desktopGeneration) => {
      try {
        await desktopPlayerCommand("done", { playback_id: token }, librarySource);
        if (isCurrent() && releaseGeneration === desktopGeneration && !fallbackRequested) {
          status.textContent = "Desktop playback dismissed.";
        }
      }
      catch (error) {
        if (!isCurrent() || releaseGeneration !== desktopGeneration || fallbackRequested) return;
        // A newer playback owns the shared window; its token must not be stopped.
        if (error.status === 409) {
          status.textContent = "The desktop window now belongs to another playback.";
        } else {
          playbackId = token;
          fallbackRequested = true;
          doneButton.hidden = false;
          playButton.disabled = true;
          status.textContent = `Could not dismiss desktop playback: ${error.message}`;
        }
      }
    };
    const done = () => {
      desktopGeneration += 1;
      if (pendingLaunch) pendingLaunch.cancelGeneration = desktopGeneration;
      clearPoll();
      const token = playbackId;
      const wasRequested = fallbackRequested;
      playbackId = null;
      fallbackRequested = false;
      playIntent = false;
      doneButton.hidden = true;
      playButton.disabled = desktopAvailable === false;
      if (wasRequested && isCurrent()) status.textContent = "Dismissing desktop playback…";
      return token ? release(token) : Promise.resolve();
    };
    originalVideo.desktop = { done, doneAndWait: async () => {
      const launch = pendingLaunch;
      await done();
      if (launch) await launch.finished;
      return !fallbackRequested;
    } };
    const displayDesktopStatus = snapshot => {
      if (!isCurrent() || !fallbackRequested) return;
      if (snapshot.playback_id !== playbackId) {
        clearPoll();
        playbackId = null;
        fallbackRequested = false;
        doneButton.hidden = true;
        playButton.disabled = false;
        status.textContent = "Desktop playback is no longer assigned to this scene.";
        return;
      }
      const messages = {
        starting: "Opening the original recording in the desktop player…",
        playing: "Playing original recording in the desktop pop-out.",
        paused: "Desktop playback paused. Restore the pop-out to continue.",
        ended: "Original recording ended. The pop-out is minimized.",
        stopped: "Desktop playback stopped.",
        closed: "Desktop player closed.",
        idle: "Desktop player is idle.",
      };
      status.textContent = snapshot.state === "error"
        ? `Desktop playback unavailable: ${snapshot.error || "The player failed."}`
        : messages[snapshot.state] || "Desktop playback status unavailable.";
      playButton.disabled = ["starting", "playing", "paused"].includes(snapshot.state);
      doneButton.hidden = !["starting", "playing", "paused"].includes(snapshot.state);
      if (!["starting", "playing", "paused"].includes(snapshot.state)) {
        clearPoll();
        fallbackRequested = false;
        return;
      }
      const requestGeneration = desktopGeneration;
      desktopTimer = setTimeout(async () => {
        desktopTimer = null;
        try {
          const current = await apiGet("/api/media/desktop-player/status", librarySource);
          if (requestGeneration === desktopGeneration) displayDesktopStatus(current);
        } catch (error) {
          if (isCurrent() && requestGeneration === desktopGeneration) {
            status.textContent = "Desktop playback status unavailable. Use the pop-out controls or Done.";
            playButton.disabled = true;
          }
        }
      }, 1000);
    };
    const launchDesktop = async () => {
      if (!isCurrent() || !unsupported || !playIntent || fallbackRequested || desktopAvailable === false) return;
      if (sceneId === null || sceneId === undefined || String(sceneId).trim() === "") {
        status.textContent = "Desktop playback unavailable: this result has no scene identity.";
        playButton.disabled = true;
        return;
      }
      clearPoll();
      fallbackRequested = true;
      const requestGeneration = ++desktopGeneration;
      const launch = { cancelGeneration: null };
      let finishLaunch;
      launch.finished = new Promise(resolve => { finishLaunch = resolve; });
      pendingLaunch = launch;
      video.pause();
      pauseOriginalAudio();
      ttsStop();
      playButton.disabled = true;
      doneButton.hidden = false;
      status.textContent = "Opening the original recording in the desktop player…";
      try {
        const snapshot = await desktopPlayerCommand("play", {
          video_id: decodeURIComponent(sourceMatch[1]), scene_id: String(sceneId),
          window: desktopPlayerWindow(keyframe && !keyframe.hidden ? keyframe : video),
        }, librarySource);
        if (pendingLaunch === launch) pendingLaunch = null;
        if (!isCurrent() || requestGeneration !== desktopGeneration) {
          if (snapshot.playback_id) await release(snapshot.playback_id, launch.cancelGeneration);
          return;
        }
        if (!snapshot.available || !snapshot.playback_id) throw new Error(snapshot.error || "The desktop player is unavailable.");
        playbackId = snapshot.playback_id;
        displayDesktopStatus(snapshot);
      } catch (error) {
        if (pendingLaunch === launch) pendingLaunch = null;
        if (!isCurrent() || requestGeneration !== desktopGeneration) return;
        fallbackRequested = false;
        playIntent = false;
        playButton.disabled = false;
        doneButton.hidden = true;
        status.textContent = `Desktop playback unavailable: ${error.message}`;
      } finally {
        finishLaunch();
      }
    };
    const updateStatus = message => {
      if (isCurrent() && !failed && !fallbackRequested) status.textContent = message;
    };
    const fail = (message, allowDesktop = false) => {
      if (!isCurrent() || failed) return;
      failed = true;
      unsupported = allowDesktop;
      video.pause();
      video.hidden = true;
      if (keyframe) keyframe.hidden = false;
      status.textContent = message;
      playButton.disabled = !allowDesktop;
      if (allowDesktop) {
        if (playIntent) launchDesktop();
        else {
          const checkGeneration = desktopGeneration;
          apiGet("/api/media/desktop-player/status", librarySource).then(snapshot => {
            if (!isCurrent() || fallbackRequested || checkGeneration !== desktopGeneration) return;
            desktopAvailable = snapshot.available === true;
            playButton.disabled = !desktopAvailable;
            status.textContent = desktopAvailable
              ? `${message} Use Play original video to open a desktop pop-out.`
              : `${message} ${snapshot.error || "Desktop playback is unavailable on this device."}`;
          }).catch(() => {
            if (isCurrent() && !fallbackRequested && checkGeneration === desktopGeneration) {
              status.textContent = `${message} Desktop playback availability could not be checked.`;
            }
          });
        }
      }
    };
    video.onloadedmetadata = () => {
      if (!isCurrent() || failed || initialSeek) return;
      if (!Number.isFinite(video.duration) || video.duration <= 0 || start >= video.duration) {
        fail("Original source video unavailable: scene start is outside the recording duration.");
        return;
      }
      try {
        video.currentTime = start;
        initialSeek = true;
        updateStatus(`Seeking to scene at ${formatTime(start)} in the original recording.`);
      } catch (error) {
        fail("Original source video could not seek to this scene.");
      }
    };
    const showVideo = () => {
      if (!isCurrent() || failed || !initialSeek || video.seeking) return;
      if (!(video.videoWidth > 0 && video.videoHeight > 0)) {
        fail("Original source video unavailable: this browser decoded no video frames. The video format may be unsupported.", true);
        return;
      }
      video.hidden = false;
      if (keyframe) keyframe.hidden = true;
      updateStatus(`Original recording ready. Scene starts at ${formatTime(start)}; use the video controls to play.`);
    };
    video.onloadeddata = showVideo;
    video.onseeked = showVideo;
    video.onplay = () => {
      if (!isCurrent() || failed) return;
      if (fallbackRequested || playbackId) done();
      playIntent = true;
      pauseOriginalAudio();
      ttsStop();
    };
    video.onplaying = () => updateStatus("Playing original source video.");
    video.onpause = () => updateStatus("Original source video paused.");
    video.onended = () => updateStatus("Original source video ended.");
    video.onerror = () => fail("Original source video could not be loaded or played. The file may be unavailable or its format unsupported by this browser.",
      video.error?.code === 3 || video.error?.code === 4);
    playButton.addEventListener("click", () => {
      if (!isCurrent() || playButton.disabled) return;
      playIntent = true;
      if (unsupported) launchDesktop();
      else video.play().catch(error => {
        if (error.name === "NotSupportedError") fail("This browser cannot play the original video format.", true);
        else updateStatus(`Original video playback could not start: ${error.message}`);
      });
    });
    doneButton.addEventListener("click", done);
    status.textContent = "Loading original source video.";
    video.src = endpoint;
    panel.appendChild(video);
    const actions = document.createElement("div");
    actions.className = "original-video-actions";
    actions.append(playButton, doneButton);
    panel.appendChild(actions);
    panel.appendChild(status);
  }

  function pauseOriginalAudio() {
    if (originalAudio.element) originalAudio.element.pause();
  }

  function resetOriginalAudio() {
    originalAudio.generation += 1;
    const audio = originalAudio.element;
    originalAudio.element = null;
    if (audio) {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    }
    const panel = document.getElementById("inspector-original-audio");
    if (panel) {
      panel.innerHTML = "";
      panel.hidden = true;
    }
  }

  function renderStandaloneSource(scene) {
    const panel = document.getElementById("inspector-original-video");
    if (!panel) return;
    const kind = scene.source_kind;
    panel.hidden = false;
    appendText(panel, "h3", `Original ${kind}`);
    const endpoint = scene.original_source_endpoint;
    if (scene.original_source_available !== true || typeof endpoint !== "string"
      || !/^\/api\/media\/video\/[^/?#]+\/source$/.test(endpoint)
      || !["image", "document", "audio"].includes(kind)) {
      appendText(panel, "p", `Original ${kind} unavailable.`);
      return;
    }
    const open = document.createElement("a");
    open.href = endpoint;
    open.target = "_blank";
    open.rel = "noopener";
    open.textContent = `Open original ${kind}`;
    panel.appendChild(open);
    if (kind === "audio") {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.preload = "metadata";
      audio.setAttribute("aria-label", "Original audio recording");
      originalVideo.element = audio;
      const status = document.createElement("p");
      status.setAttribute("role", "status");
      audio.onplay = () => { pauseOriginalAudio(); ttsStop(); };
      audio.onerror = () => { status.textContent = "Original audio could not be loaded or played."; };
      audio.src = endpoint;
      panel.appendChild(audio);
      panel.appendChild(status);
    }
  }

  function renderOriginalAudio(scene) {
    const panel = document.getElementById("inspector-original-audio");
    if (!panel) return;
    if (scene.source_kind && scene.source_kind !== "video") {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    appendText(panel, "h3", "Original scene audio");
    const status = document.createElement("p");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const endpoint = scene.original_audio_endpoint;
    if (scene.original_audio_available !== true || typeof endpoint !== "string"
      || !/^\/api\/media\/video\/[^/?#]+\/scene\/[^/?#]+\/audio$/.test(endpoint)) {
      status.textContent = "Original scene audio unavailable.";
      panel.appendChild(status);
      return;
    }

    const audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "metadata";
    audio.setAttribute("aria-label", "Original scene audio");
    const generation = originalAudio.generation;
    originalAudio.element = audio;
    const isCurrent = () => originalAudio.element === audio && originalAudio.generation === generation;
    let failed = false;
    const updateStatus = message => {
      if (isCurrent() && !failed) status.textContent = message;
    };
    audio.onplay = () => { if (isCurrent()) { pauseOriginalVideo(); ttsStop(); } };
    audio.onplaying = () => updateStatus("Playing original scene audio.");
    audio.onpause = () => updateStatus("Original scene audio paused.");
    audio.onended = () => updateStatus("Original scene audio ended.");
    audio.onerror = () => {
      if (!isCurrent()) return;
      failed = true;
      status.textContent = "Original scene audio could not be loaded or played.";
    };
    status.textContent = "Use the audio controls to play this scene's recording.";
    audio.src = endpoint;
    panel.appendChild(audio);
    panel.appendChild(status);
  }

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
      tts.activePlayAllBtn.textContent = '▶ READ TRANSCRIPT';
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
    pauseOriginalAudio();
    pauseOriginalVideo();
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

  // Helper Utility: Entity Name Normalizer (text grouping, never identity resolution)

  function normalizeEntityName(name) {
    const cleaned = String(name || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
    return cleaned;
  }

  function getCanonicalLabel(id, rawName) {
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
  async function apiGet(path, librarySource) {
    const url = typeof window !== "undefined" && window.GoodQLibrary ? window.GoodQLibrary.url(path, librarySource) : path;
    const response = await fetch(url, { method: "GET" });
    if (typeof window !== "undefined") window.GoodQLibrary?.observeResponse?.(response, path);
    if (!response.ok) {
      const error = new Error(`GET ${path} failed: ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }

  // API Call Wrapper: POST
  async function apiPost(path, body) {
    const url = typeof window !== "undefined" && window.GoodQLibrary ? window.GoodQLibrary.url(path) : path;
    const response = await fetch(url, {
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
    return raw.filter(item => typeof item === "string" || (item && typeof item === "object")).map((item) => {
      if (typeof item === "string") return { name: item, type: "generic" };
      return {
        ...item,
        name: item.label || item.name || item.text || "",
        type: item.entity_type || item.type || item.category || "generic",
      };
    }).filter(e => typeof e.name === "string" && e.name.trim());
  }

  // Read projection only: every association retains its per-scene channel support.
  // A shared label/scene is not an identity decision or a semantic relationship.
  function buildEntityGraph(scenes) {
    const nodes = new Map();
    const edges = new Map();

    scenes.forEach((scene) => {
      if (!scene || scene.id == null) return;
      const channelSources = [
        { list: scene.scene_present_entities || [], channel: "scene_present" },
        { list: scene.dialogue_mentioned_entities || [], channel: "dialogue_mentioned" },
        { list: scene.candidate_visible_people || [], channel: "candidate" },
        { list: scene.entities || [], channel: "generic" },
      ];

      const sceneEntities = new Map();

      channelSources.forEach(({ list, channel }) => {
        if (!Array.isArray(list)) return;
        list.forEach((entity) => {
          const rawName = typeof entity === "string" ? entity : (entity?.name || entity?.label || entity?.text || "");
          if (typeof rawName !== "string" || !rawName.trim()) return;
          const name = normalizeEntityName(rawName);
          const sceneLocal = /^(anonymous[ _-]|(?:male |female )?speaker[ _-]?\d|face[ _-]?\d)/.test(name);
          const id = sceneLocal ? JSON.stringify([name, String(scene.id)]) : name;
          const rawType = typeof entity === "object" ? (entity.entity_type || entity.type || "generic") : "generic";
          const node = nodes.get(id) || {
            id, label: getCanonicalLabel(name, rawName), type: rawType,
            types: [], channels: [], count: 0, sceneIds: [], observations: [],
            scopeSceneId: sceneLocal ? scene.id : null,
            scopeStart: sceneLocal ? scene.start : null,
          };
          if (!node.types.includes(rawType)) node.types.push(rawType);
          if (!node.channels.includes(channel)) node.channels.push(channel);
          if (!node.sceneIds.includes(scene.id)) node.sceneIds.push(scene.id);
          if (!node.observations.some(o => o.sceneId === scene.id && o.channel === channel &&
              JSON.stringify(o.entity) === JSON.stringify(entity))) {
            node.observations.push({ sceneId: scene.id, channel, entity });
          }
          node.count = node.sceneIds.length;
          // A generic duplicate does not erase a specific channel. Different
          // specific channels remain mixed rather than inheriting the strongest.
          const specific = node.channels.filter(c => c !== "generic");
          node.channel = specific.length > 1 ? "mixed" : (specific[0] || "generic");
          const types = node.types.filter(t => t !== "generic");
          node.type = types.length > 1 ? "mixed" : (types[0] || "generic");
          nodes.set(id, node);
          const channels = sceneEntities.get(id) || [];
          if (!channels.includes(channel)) channels.push(channel);
          sceneEntities.set(id, channels);
        });
      });

      // ── Build co-occurrence edges across all entities in this scene ──
      const ids = Array.from(sceneEntities.keys()).sort();
      for (let i = 0; i < ids.length; i += 1) {
        for (let j = i + 1; j < ids.length; j += 1) {
          const a = ids[i];
          const b = ids[j];
          const key = JSON.stringify([a, b]);
          const existing = edges.get(key) || { source: a, target: b, relation: "shared_scene", weight: 0, sceneIds: [], evidence: [] };
          const support = existing.evidence.find(e => e.sceneId === scene.id);
          if (support) {
            support.sourceChannels = [...new Set([...support.sourceChannels, ...sceneEntities.get(a)])];
            support.targetChannels = [...new Set([...support.targetChannels, ...sceneEntities.get(b)])];
          } else {
            existing.sceneIds.push(scene.id);
            existing.evidence.push({ sceneId: scene.id, sourceChannels: sceneEntities.get(a), targetChannels: sceneEntities.get(b) });
          }
          existing.weight = existing.sceneIds.length;
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

    // 2D Multi-Ring Concentric Tactical Layout (sorted by importance/recurrence)
    const channelWeight = (n) => {
      const ch = n.channel || "generic";
      if (ch === "mixed" || ch === "scene_present") return 4;
      if (ch === "dialogue_mentioned") return 3;
      if (n.type === "location" || n.type === "event") return 2;
      if (ch === "candidate") return 1;
      return 0;
    };

    const ranked = nodes
      .map((node, idx) => ({ node, idx }))
      .sort((a, b) => {
        const cwDiff = channelWeight(b.node) - channelWeight(a.node);
        if (cwDiff !== 0) return cwDiff;
        return (b.node.count || 0) - (a.node.count || 0);
      });

    if (nodes.length <= 18) {
      const radius = 128;
      ranked.forEach((entry, rankIdx) => {
        const angle = (rankIdx / (ranked.length || 1)) * 2 * Math.PI - Math.PI / 2;
        entry.node.x = radius * Math.cos(angle);
        entry.node.y = radius * Math.sin(angle);
        entry.node._layoutTier = 0;
      });
    } else {
      const innerCount = Math.min(7, Math.max(4, Math.ceil(nodes.length * 0.08)));
      const middleCount = Math.min(15, Math.max(8, Math.ceil(nodes.length * 0.18)));
      const innerRing = ranked.slice(0, innerCount);
      const middleRing = ranked.slice(innerCount, innerCount + middleCount);
      const outerRing = ranked.slice(innerCount + middleCount);

      innerRing.forEach((entry, i) => {
        const angle = (i / (innerRing.length || 1)) * 2 * Math.PI - Math.PI / 2;
        const r = 54;
        entry.node.x = r * Math.cos(angle);
        entry.node.y = r * Math.sin(angle) - 8;
        entry.node._layoutTier = 0;
      });

      middleRing.forEach((entry, i) => {
        const angle = (i / (middleRing.length || 1)) * 2 * Math.PI - Math.PI / 2 + 0.22;
        const r = 104 + (i % 2) * 6;
        entry.node.x = r * Math.cos(angle);
        entry.node.y = r * Math.sin(angle) - 8;
        entry.node._layoutTier = 1;
      });

      outerRing.forEach((entry, i) => {
        const angle = (i / (outerRing.length || 1)) * 2 * Math.PI - Math.PI / 2;
        const r = 148 + (i % 2) * 14;
        entry.node.x = r * Math.cos(angle);
        entry.node.y = r * Math.sin(angle) - 8;
        entry.node._layoutTier = 2;
      });
    }

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

    const isEffects = document.getElementById("crt-screen").classList.contains("no-sfx") === false;
    const hoveredId = state.hoveredNodeId || null;
    const activeNeighborIds = new Set();

    // Draw Edges (Connections)
    state.graph.edges.forEach((edge) => {
      const sourceNode = state.graph.nodes.find((n) => n.id === edge.source);
      const targetNode = state.graph.nodes.find((n) => n.id === edge.target);
      if (!sourceNode || !targetNode) return;

      const isSelected = (state.selectedEntities && state.selectedEntities.includes(edge.source)) || 
                         (state.selectedEntities && state.selectedEntities.includes(edge.target)) ||
                         (hoveredId && (edge.source === hoveredId || edge.target === hoveredId));
      if (isSelected) {
        activeNeighborIds.add(edge.source);
        activeNeighborIds.add(edge.target);
      }

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
        ctx.strokeStyle = applyOpacity("rgba(0, 212, 255, 0.78)", opacityMultiplier);
        ctx.lineWidth = Math.min(8, 2 + edge.weight * 2);
      } else {
        const edgeColor = document.body.classList.contains("theme-day")
          ? "rgba(71, 85, 105, 0.25)"
          : "rgba(148, 163, 184, 0.22)";
        ctx.strokeStyle = applyOpacity(edgeColor, opacityMultiplier);
        ctx.lineWidth = Math.min(3, 0.6 + edge.weight / 2);
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
      const isSelected = (state.selectedEntities && state.selectedEntities.includes(node.id)) || (hoveredId === node.id);
      const ch = node.channel || "generic";

      // ── Channel color scheme (Obsidian / God's Eye View Tactical Studio) ──
      const isDayTheme = document.body.classList.contains("theme-day");

      const channelStroke = isSelected ? (isDayTheme ? "#0284c7" : "#00d4ff") :
        ch === "mixed"               ? (isDayTheme ? "#7c3aed" : "#c084fc") :
        ch === "scene_present"       ? (isDayTheme ? "#0284c7" : "#38bdf8") :
        ch === "dialogue_mentioned"  ? (isDayTheme ? "#2563eb" : "#60a5fa") :
        ch === "candidate"           ? (isDayTheme ? "#d97706" : "#fbbf24") :
        node.type === "location"     ? (isDayTheme ? "#0891b2" : "#22d3ee") :
        node.type === "event"        ? (isDayTheme ? "#ea580c" : "#fb7185") :
                                       (isDayTheme ? "#0d9488" : "#34d399");

      const channelFill = isSelected ? (isDayTheme ? "rgba(2, 132, 199, 0.9)" : "rgba(0, 212, 255, 0.95)") :
        ch === "scene_present"       ? (isDayTheme ? "rgba(2, 132, 199, 0.22)" : "rgba(56, 189, 248, 0.25)") :
        ch === "dialogue_mentioned"  ? (isDayTheme ? "rgba(37, 99, 235, 0.10)" : "rgba(96, 165, 250, 0.12)") :
        ch === "candidate"           ? (isDayTheme ? "rgba(217, 119, 6, 0.16)" : "rgba(251, 191, 36, 0.20)") :
                                       (isDayTheme ? "rgba(255, 255, 255, 0.92)" : "rgba(9, 13, 20, 0.94)");

      const channelLabel = isSelected ? (isDayTheme ? "#0369a1" : "#38bdf8") :
        ch === "mixed"               ? (isDayTheme ? "#6d28d9" : "#d8b4fe") :
        ch === "scene_present"       ? (isDayTheme ? "#0369a1" : "#7dd3fc") :
        ch === "dialogue_mentioned"  ? (isDayTheme ? "#1d4ed8" : "#93c5fd") :
        ch === "candidate"           ? (isDayTheme ? "#b45309" : "#fcd34d") :
                                       (isDayTheme ? "#1e293b" : "#cbd5e1");

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

      // Text label (hide/fade on back hemisphere, and declutter outer single-scene labels when zoomed out)
      const inFront3D = !(state.graphMode === "3D" && node.rotatedZ < -10);
      const isPrimaryLabel =
        state.graphMode === "3D" ||
        isSelected ||
        activeNeighborIds.has(node.id) ||
        state.graph.nodes.length <= 22 ||
        state.canvasScale >= 1.32 ||
        (node._layoutTier !== undefined ? node._layoutTier <= 1 : (node.count || 0) >= 3);

      if (inFront3D && isPrimaryLabel) {
        const rawText = objectEvidenceLabel(node);
        const displayText = (!isSelected && state.canvasScale < 1.32 && rawText.length > 22)
          ? `${rawText.slice(0, 20)}…`
          : rawText;
        ctx.font = isSelected
          ? "600 11.5px 'Outfit', system-ui, sans-serif"
          : (ch === "scene_present" ? "600 10.5px 'Outfit', system-ui, sans-serif" : "500 10px 'Outfit', system-ui, sans-serif");
        ctx.textAlign = "center";
        ctx.shadowBlur = 0;
        const textWidth = ctx.measureText(displayText).width;
        const pillPadX = 4;
        const pillY = ny + radius + 3;
        ctx.fillStyle = isDayTheme ? "rgba(248, 250, 252, 0.82)" : "rgba(9, 13, 20, 0.78)";
        ctx.fillRect(nx - textWidth / 2 - pillPadX, pillY, textWidth + pillPadX * 2, 13);
        ctx.fillStyle = labelColor;
        ctx.fillText(displayText, nx, ny + radius + 13);
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
      let suffix = "";
      if ((video.source_kind || "video") === "video" && video.phase6_complete === false) {
        suffix = " [PARTIAL INDEX]";
      }
      const sourceLabel = video.source_kind && video.source_kind !== "video" ? ` [${video.source_kind}]` : "";
      option.textContent = (video.title || video.video_id || video.id) + sourceLabel + suffix;
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
      label.textContent = `${objectEvidenceLabel(node)} (${node.count})`;
      
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

  function appendIdentitySearchEvidence(container, sceneId) {
    if (!state.searchActive) return;
    const result = state.searchResults.find(res => String(res.scene_id) === String(sceneId));
    if (!result || !Array.isArray(result.identity_evidence)) return;
    result.identity_evidence.forEach(item => {
      if (!item || typeof item.display_name !== "string" || !item.display_name.trim()) return;
      if (!["appearance", "voice", "mention"].includes(item.strength)) return;
      const evidence = document.createElement("p");
      evidence.className = "scene-card-identity";
      evidence.textContent = `${item.display_name}: ${(item.evidence_types || [item.strength]).map(type => ({appearance: "face-backed appearance", voice: "reviewed voice", mention: "transcript mention only"}[type])).filter(Boolean).join("; ")}`;
      container.appendChild(evidence);
    });
    if (result.identity_only === true) {
      const limit = document.createElement("p");
      limit.className = "scene-card-identity-limit";
      limit.textContent = "Person match only; event relevance unverified";
      container.appendChild(limit);
    }
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
        if (state.activeSearchTab !== "narrative") {
          parts.push(`${state.searchResults.length} ranked candidates`);
        }
        parts.push(`"${state.lastQuery}"`);
      }
      if (state.selectedEntities && state.selectedEntities.length > 0) {
        const labels = state.selectedEntities.map(id => {
          const node = state.graph.nodes.find(n => n.id === id);
          return node ? objectEvidenceLabel(node) : id;
        });
        parts.push(labels.join(" + "));
      }
      heading.textContent = parts.length > 0
        ? `Timeline  //  ${parts.join("  ·  ")}`
        : "Timeline  //  All Scenes";
    }

    let scenesToRender = [];
    const isNarrativeSearchActive = state.searchActive && state.activeSearchTab === "narrative";

    if (isNarrativeSearchActive) {
      // In narrative mode, render search results directly, preserving order
      scenesToRender = state.searchResults.map((res) => {
        const found = state.scenes.find((s) => {
          if (!s) return false;
          const sId = String(s.id ?? "").trim().toLowerCase();
          const rId = String(res.scene_id ?? "").trim().toLowerCase();
          return sId && rId && sId === rId;
        });
        const resolvedSummary = res.summary || (found ? found.summary : "No description available.");
        const resolvedSummaryMeta = (!res.summary && found && found.summary_meta)
          ? found.summary_meta
          : res.summary_meta
          ? res.summary_meta
          : (res.summary && found && found.summary === res.summary && found.summary_meta)
          ? found.summary_meta
          : res.summary
          ? {
              source: "unknown",
              provenance_status: "unknown",
              qualification: "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels).",
            }
          : {
              source: "none",
              provenance_status: "none",
              qualification: null,
            };
        return {
          id: res.scene_id,
          start: res.start_time,
          end: typeof res.end_time === "number" ? res.end_time : 0.0,
          summary: resolvedSummary,
          summary_meta: resolvedSummaryMeta,
          source_kind: res.source_kind || "video",
          document_text: res.document_text || null,
          document_meta: res.document_meta || null,
          original_source_endpoint: res.original_source_endpoint,
          original_source_available: res.original_source_available === true,
          keyframe_url: found ? found.keyframe_url : resolveKeyframeUrl(res.evidence ? res.evidence.artifact_paths : null, res.source_file),
          entities: Array.isArray(res.entities) ? res.entities.map(e => ({ name: e, type: "generic" })) : (found ? found.entities : []),
          dialogue: res.evidence && typeof res.evidence.transcript === "string" ? [{ text: res.evidence.transcript }] : (found ? found.dialogue : []),
          transcript: (res.evidence && res.evidence.transcript) || "",
          clap_meta: res.clap_meta || (res.context && res.context.clap_meta) || null,
          transcript_meta: res.transcript_meta || (res.context && res.context.transcript_meta) || null,
          transcript_outcome: res.transcript_outcome || (res.context && res.context.transcript_outcome) || null,
          transcript_outcome_reason: res.transcript_outcome_reason || (res.context && res.context.transcript_outcome_reason) || null,
          diarization_status: res.diarization_status || null,
          diarization_note: res.diarization_note || null,
          emotion_status: res.emotion_status || null,
          emotion_note: res.emotion_note || null,
          source_file: res.source_file || "",
          original_audio_endpoint: res.original_audio_endpoint,
          original_audio_available: res.original_audio_available === true,
          original_video_endpoint: res.original_video_endpoint,
          original_video_available: res.original_video_available === true,
          sentiment_label: found ? found.sentiment_label : "NEUTRAL",
          audio_emotion: res.audio_emotion || (found ? found.audio_emotion : null),
          emotion_segments: res.emotion_segments || [],
          emotion_input: res.emotion_input || null,
          sound_events: res.sound_events || [],
          audio_evidence: res.audio_evidence,
          sound_event_meta: res.sound_event_meta || null,
          content_state: found ? found.content_state : "signal",
          transcript_entity_disagreements: found ? found.transcript_entity_disagreements : [],
          phase6_complete: res.phase6_complete,
          temporal_distance_from_previous: typeof res.temporal_distance_from_previous === "number" ? res.temporal_distance_from_previous : 0.0,
          semantic_similarity_from_previous: typeof res.semantic_similarity_from_previous === "number" ? res.semantic_similarity_from_previous : 0.0
        };
      });
    } else {
      scenesToRender = state.scenes.filter((scene) => {
        // 1. If search is active, check if this scene is in search results
        if (state.searchActive) {
          const isMatched = state.searchResults.some((res) => {
            const rId = String(res.scene_id ?? "").trim().toLowerCase();
            const sId = String(scene.id ?? "").trim().toLowerCase();
            if (rId && sId && rId === sId) {
              scene.phase6_complete = res.phase6_complete;
              return true;
            }
            return false;
          });
          if (!isMatched) return false;
        }

        // 2. Entity filter: check ALL channel arrays so Sprint 2 channels are included
        if (state.selectedEntities && state.selectedEntities.length > 0) {
          const hasAllSelected = state.selectedEntities.every(entityId =>
            state.graph.nodes.find(n => n.id === entityId)?.sceneIds.includes(scene.id));
          if (!hasAllSelected) return false;
        }

        return true;
      });
    }

    if (state.searchActive && !isNarrativeSearchActive) {
      const ranks = new Map(state.searchResults.map((res, index) => [String(res.scene_id).trim().toLowerCase(), index]));
      scenesToRender.sort((a, b) => ranks.get(String(a.id).trim().toLowerCase()) - ranks.get(String(b.id).trim().toLowerCase()));
    }

    scenesToRender.forEach((scene, index) => {
      // If it's a narrative search and index > 0, insert a narrative connector line/bubble
      if (isNarrativeSearchActive && index > 0) {
        const connector = document.createElement("div");
        connector.className = "narrative-connector";

        const line1 = document.createElement("div");
        line1.className = "connector-line";
        connector.appendChild(line1);

        const metrics = document.createElement("div");
        metrics.className = "connector-metrics";

        const gapVal = scene.temporal_distance_from_previous;
        const gapSpan = document.createElement("span");
        gapSpan.className = "metric-gap";
        gapSpan.textContent = gapVal > 0 ? `+${gapVal}s` : "0.0s";
        metrics.appendChild(gapSpan);

        const simVal = scene.semantic_similarity_from_previous;
        const simSpan = document.createElement("span");
        simSpan.className = "metric-sim";
        simSpan.textContent = `~${simVal.toFixed(4)}`;
        metrics.appendChild(simSpan);

        connector.appendChild(metrics);

        const line2 = document.createElement("div");
        line2.className = "connector-line";
        connector.appendChild(line2);

        const arrow = document.createElement("span");
        arrow.className = "connector-arrow";
        arrow.textContent = "▶";
        connector.appendChild(arrow);

        grid.appendChild(connector);
      }

      const card = document.createElement("article");
      const isSelected = scene.id != null && state.selectedSceneId != null &&
        (String(scene.id).trim().toLowerCase() === String(state.selectedSceneId).trim().toLowerCase());
      const isMatched = state.searchResults.some((res) => {
        const rId = String(res.scene_id ?? "").trim().toLowerCase();
        const sId = String(scene.id ?? "").trim().toLowerCase();
        return rId && sId && rId === sId;
      });

      const passesIntel = scenePassesIntelFilter(scene);
      card.className = `scene-card ${isSelected ? "selected" : ""} ${isMatched ? "matched" : ""} ${state.intelFilter && !passesIntel ? "intel-dim" : ""}`;
      card.setAttribute("data-scene-id", scene.id);
      if (isMatched) {
        card.setAttribute("data-search-label", `RESULT #${index + 1}`);
      }

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
      timeTag.textContent = ["image", "document"].includes(scene.source_kind)
        ? scene.source_kind.toUpperCase() : `${formatTime(scene.start)} - ${formatTime(scene.end)}`;
      frame.appendChild(timeTag);
      card.appendChild(frame);

      // Metadata card body
      const body = document.createElement("div");
      body.className = "scene-card-body";

      const cardId = document.createElement("div");
      cardId.className = "scene-card-id";
      if (isNarrativeSearchActive && scene.source_file) {
        cardId.textContent = `${scene.source_file.replace(/\.[^/.]+$/, "")} // SCENE #${scene.id}`;
      } else {
        cardId.textContent = `SCENE #${scene.id}`;
      }
      
      const activeVideo = state.videos.find(v => (v.video_id || v.id) === state.activeVideoId);
      const sourceKind = scene.source_kind || (activeVideo && activeVideo.source_kind) || "video";
      const isVideoPartial = activeVideo && activeVideo.phase6_complete === false;
      const isPartial = sourceKind === "video" && ((scene.phase6_complete === false) || (scene.phase6_complete === undefined && isVideoPartial));
      if (isPartial) {
        const partialBadge = document.createElement("span");
        partialBadge.className = "ingestion-active-badge blink";
        partialBadge.style.fontSize = "9px";
        partialBadge.style.padding = "1px 4px";
        partialBadge.style.marginLeft = "6px";
        partialBadge.textContent = "[PARTIAL INDEX]";
        cardId.appendChild(partialBadge);
      }
      
      body.appendChild(cardId);

      const summary = document.createElement("p");
      summary.className = "scene-card-summary";
      summary.textContent = scene.summary || "No description returned.";
      body.appendChild(summary);
      const cardQualification = (scene.summary_meta && scene.summary_meta.qualification)
        ? scene.summary_meta.qualification
        : (scene.summary && scene.summary !== "No description available." && scene.summary !== "No description returned.")
        ? (scene.visual_caption && scene.summary === scene.visual_caption
            ? "Summary source: visual caption (unverified model observation; not confirmed scene fact)."
            : "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels).")
        : null;
      if (cardQualification) {
        const summaryQual = document.createElement("p");
        summaryQual.className = "scene-card-summary-qualification";
        summaryQual.textContent = cardQualification;
        body.appendChild(summaryQual);
      }
      appendIdentitySearchEvidence(body, scene.id);

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
        const score = scene.sentiment_score ?? scene.sentiment?.score;
        chip.textContent = `Text: ${sl}${Number.isFinite(score) ? ` · ${(score * 100).toFixed(1)}% score` : ""}`;
        chip.title = "Text analysis estimate; a near-even binary score is uncertain.";
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
        selectScene(scene.id, scene);
      });

      grid.appendChild(card);
    });
  }

  // Select Scene and Update Inspector (preserves entity filter)
  function selectScene(sceneId, mediaSource = null) {
    state.selectedSceneId = sceneId;
    state.selectedOriginalMedia = mediaSource || (state.activeSearchTab === "narrative"
      ? state.searchResults.find(result => String(result.scene_id) === String(sceneId)) || {}
      : null);
    state.selectedEntity = null;  // Clear single entity highlight but keep multi-filter
    renderTimelineGrid();
    drawGraph();
    renderInspector();
    
    // Auto-scroll timeline to target card
    const selectedCard = document.querySelector(`.scene-card[data-scene-id="${sceneId}"]`);
    if (selectedCard) {
      selectedCard.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }

    // Forensic logging of claims verification / scene selection data trail
    let scene = state.scenes.find((s) => {
      if (!s) return false;
      const sId = String(s.id ?? "").trim().toLowerCase();
      const selId = String(sceneId ?? "").trim().toLowerCase();
      return (sId && selId && sId === selId) || (s.scene_index != null && String(s.scene_index) === selId);
    });

    if (!scene && state.searchResults && state.searchResults.length > 0) {
      const res = state.searchResults.find((r) => {
        const rId = String(r.scene_id ?? "").trim().toLowerCase();
        const selId = String(sceneId ?? "").trim().toLowerCase();
        return rId && selId && rId === selId;
      });
      if (res) {
        scene = {
          id: res.scene_id,
          start: res.start_time,
          end: typeof res.end_time === "number" ? res.end_time : 0.0,
          summary: res.summary || "No description available.",
          source_file: res.source_file || "",
          sentiment_label: "NEUTRAL",
          audio_emotion: res.audio_emotion || null,
          emotion_segments: res.emotion_segments || [],
          emotion_input: res.emotion_input || null,
          sound_events: res.sound_events || [],
          audio_evidence: res.audio_evidence,
          sound_event_meta: res.sound_event_meta || null,
        };
      }
    }

    if (scene) {
      const timeRangeStr = `${formatTime(scene.start)} - ${formatTime(scene.end)}`;
      const source = scene.source_file || state.activeVideoId;
      const shortId = scene.id ? String(scene.id).substring(0, 8) : "N/A";
      logDataTrail(
        `Select Scene #${shortId}`,
        "Scene inspection / source linkage",
        state.activeVideoId,
        source,
        `Selected scene evidence: "${scene.summary || 'No description available.'}"`,
        null,
        timeRangeStr
      );
    }
  }

  // Single Select an Entity (clears other selections)
  function singleSelectEntity(entityId, skipScrollChecklist = false) {
    entityId = resolveGraphEntityId(entityId);
    if (entityId == null) return;
    state.selectedEntities = [entityId];
    state.selectedEntity = entityId;
    // Keep selected scene active so keyframe remains visible

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
    // Keep selected scene active so keyframe remains visible

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
    entityId = resolveGraphEntityId(entityId);
    if (entityId == null) return;
    if (!state.selectedEntities) {
      state.selectedEntities = [];
    }
    state.selectedEntities = state.selectedEntities.filter(id => id !== entityId);
    state.selectedEntity = state.selectedEntities.length > 0 ? state.selectedEntities[state.selectedEntities.length - 1] : null;
    // Keep selected scene active so keyframe remains visible

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

  function resolveGraphEntityId(entityId) {
    if (state.graph.nodes.some(n => n.id === entityId)) return entityId;
    const matches = state.graph.nodes.filter(n => normalizeEntityName(n.label) === entityId &&
      (n.scopeSceneId == null || n.scopeSceneId === state.selectedSceneId));
    return matches.length === 1 ? matches[0].id : (matches.length ? null : entityId);
  }

  function graphChannelLabel(channel) {
    return { scene_present: "Scene presence claim", dialogue_mentioned: "Dialogue mention",
      candidate: "Visibility candidate", generic: "Other extracted record" }[channel] || "Unclassified record";
  }

  function openGraphEvidence(sceneId) {
    const scene = state.scenes.find(s => s.id === sceneId);
    if (!scene) return;
    // An explicit evidence jump must survive an older pending search and make
    // the supporting scene visible even when it is outside the query/filter.
    state.searchGeneration = (state.searchGeneration || 0) + 1;
    state.temporalSummaryGeneration = (state.temporalSummaryGeneration || 0) + 1;
    state.intelFilter = null;
    state.lastQuery = "";
    const status = document.getElementById("search-status");
    if (status) { status.textContent = ""; status.hidden = true; }
    const narrative = document.getElementById("narrative-summary-container");
    if (narrative) { narrative.textContent = ""; narrative.hidden = true; }
    resetAllFilters();
    renderVideoIntelPanel();
    selectScene(sceneId, scene);
    switchInspectorTab("entities");
  }

  function renderGraphEvidence(container, node, edge = null) {
    if (!container) return;
    const ids = edge ? edge.sceneIds : node.sceneIds;
    const channelIconMap = {
      scene_present: "👁",
      dialogue_mentioned: "💬",
      candidate: "◇",
      generic: "🏷",
    };
    const getSceneSpokenText = (scene) => {
      if (typeof scene.transcript === "string" && scene.transcript.trim()) return scene.transcript.trim();
      if (Array.isArray(scene.dialogue) && scene.dialogue.length > 0) {
        return scene.dialogue.map(d => (d && typeof d.text === "string" ? d.text.trim() : "")).filter(Boolean).join(" ").trim();
      }
      return "";
    };
    const stripCaptionBoilerplate = (str) => {
      const cleaned = String(str || "").trim().replace(/^the image (?:depicts|shows|features)\s+(?:a\s+(?:close-up\s+(?:scene|shot|view)\s+of\s+)?)?/i, "");
      return cleaned ? cleaned.charAt(0).toUpperCase() + cleaned.slice(1) : String(str || "").trim();
    };
    const extractSceneHook = (scene, observations, labelText) => {
      const cleanLabel = String(labelText || "").replace(/\s*\(unconfirmed object\)\s*$/i, "").trim().toLowerCase();
      const rawTranscript = getSceneSpokenText(scene);
      if (rawTranscript) {
        const sentences = rawTranscript.split(/(?<=[.!?])\s+|\n+/).map(s => s.trim()).filter(Boolean);
        const matched = cleanLabel
          ? sentences.find(s => s.toLowerCase().includes(cleanLabel))
          : null;
        const chosen = matched || sentences[0] || rawTranscript;
        const clipped = chosen.length > 68 ? `${chosen.slice(0, 66).trim()}…` : chosen;
        return `"${clipped}"`;
      }
      const summaryText = typeof scene.summary === "string" ? stripCaptionBoilerplate(scene.summary) : "";
      if (summaryText && summaryText !== "No description available." && summaryText !== "No description returned.") {
        return summaryText.length > 68 ? `${summaryText.slice(0, 66).trim()}…` : summaryText;
      }
      const captionText = typeof scene.visual_caption === "string" ? stripCaptionBoilerplate(scene.visual_caption) : "";
      if (captionText) {
        return captionText.length > 68 ? `${captionText.slice(0, 66).trim()}…` : captionText;
      }
      for (const obs of observations) {
        const rec = typeof obs.entity === "object" && obs.entity ? obs.entity : {};
        const props = rec.properties || {};
        const ctx = rec.evidence || props.evidence || rec.context || props.context;
        if (typeof ctx === "string" && ctx.trim()) {
          const t = ctx.trim();
          return t.length > 68 ? `${t.slice(0, 66).trim()}…` : t;
        }
      }
      return "";
    };

    ids.forEach(sceneId => {
      const scene = state.scenes.find(s => s.id === sceneId);
      if (!scene) return;
      const observations = (node.observations || []).filter(o => o.sceneId === sceneId);
      const channels = [...new Set(observations.map(o => o.channel))];
      const specificChannels = channels.filter(c => c !== "generic");
      const displayChannels = specificChannels.length > 0 ? specificChannels : channels;
      const icons = displayChannels.map(c => channelIconMap[c] || "•").join(" ");
      const hook = extractSceneHook(scene, observations, node.label || node.id);
      const emoSuffix = typeof scene.audio_emotion === "string" && scene.audio_emotion.trim()
        ? ` · ◎ ${scene.audio_emotion.trim()}`
        : "";

      const row = document.createElement("details");
      row.className = "graph-evidence-row";
      const range = scene.source_kind === "image" ? "Image" : scene.source_kind === "document"
        ? "Document passage" : `${formatTime(scene.start)}–${formatTime(scene.end)}`;
      const summaryLabel = hook
        ? `${range} · ${icons} ${hook}${emoSuffix}`
        : `${range} · ${icons} ${displayChannels.map(graphChannelLabel).join("; ")}${emoSuffix}`;
      appendText(row, "summary", summaryLabel);

      // Rich mini-overview card inside the expanded row
      const overviewBox = document.createElement("div");
      overviewBox.className = "graph-scene-overview";
      const desc = (scene.summary && scene.summary !== "No description available." && scene.summary !== "No description returned.")
        ? scene.summary
        : (scene.visual_caption || "");
      if (desc) {
        appendText(overviewBox, "p", `📷 Scene: ${desc}`, "graph-scene-desc");
      }
      const spokenText = getSceneSpokenText(scene);
      if (spokenText) {
        const cleanLabel = String(node.label || node.id || "").replace(/\s*\(unconfirmed object\)\s*$/i, "").trim().toLowerCase();
        const sentences = spokenText.split(/(?<=[.!?])\s+|\n+/).map(s => s.trim()).filter(Boolean);
        const matchedIdx = cleanLabel ? sentences.findIndex(s => s.toLowerCase().includes(cleanLabel)) : -1;
        const excerptSource = matchedIdx >= 0
          ? sentences.slice(Math.max(0, matchedIdx - 1), matchedIdx + 2).join(" ")
          : spokenText;
        const snippet = excerptSource.length > 200 ? `${excerptSource.slice(0, 198).trim()}…` : excerptSource;
        appendText(overviewBox, "p", `🗣 Dialogue: "${snippet}"`, "graph-scene-quote");
      }
      const coEntities = [];
      const selfNorm = String(node.label || node.id || "").toLowerCase();
      [
        ...(scene.scene_present_entities || []),
        ...(scene.dialogue_mentioned_entities || []),
        ...(scene.candidate_visible_people || []),
        ...(scene.entities || []),
      ].forEach(ent => {
        const raw = typeof ent === "string" ? ent : (ent?.name || ent?.label || ent?.text || "");
        if (!raw || typeof raw !== "string") return;
        const clean = raw.trim();
        if (!clean || clean.toLowerCase() === selfNorm) return;
        if (!coEntities.some(x => x.toLowerCase() === clean.toLowerCase())) coEntities.push(clean);
      });
      const metaBits = [];
      if (coEntities.length > 0) metaBits.push(`👥 Also in scene: ${coEntities.slice(0, 6).join(", ")}${coEntities.length > 6 ? ` (+${coEntities.length - 6})` : ""}`);
      if (scene.sentiment_label) metaBits.push(`Text sentiment estimate: ${scene.sentiment_label}`);
      if (typeof scene.audio_emotion === "string" && scene.audio_emotion) metaBits.push(`Emotion: ${scene.audio_emotion}`);
      if (metaBits.length > 0) {
        appendText(overviewBox, "p", metaBits.join("  ·  "), "graph-scene-context-line");
      }
      if (overviewBox.children.length > 0) {
        row.appendChild(overviewBox);
      }

      const open = document.createElement("button");
      open.className = "retro-btn-mini graph-open-scene-btn";
      open.textContent = `Open scene evidence ${range}`;
      open.addEventListener("click", () => openGraphEvidence(sceneId));
      row.appendChild(open);

      // Compact provenance footer (preserves exact audit strings and unit test expectations)
      const provBox = document.createElement("div");
      provBox.className = "graph-evidence-provenance";
      if (edge) {
        const otherId = edge.source === node.id ? edge.target : edge.source;
        const other = state.graph.nodes.find(n => n.id === otherId);
        const support = edge.evidence.find(e => e.sceneId === sceneId);
        const otherChannels = edge.source === node.id ? support.targetChannels : support.sourceChannels;
        appendText(provBox, "p", `${other ? objectEvidenceLabel(other) : otherId}: ${otherChannels.map(graphChannelLabel).join("; ")}`);
      }
      const filteredObs = observations.length > 1 && observations.some(o => o.channel !== "generic")
        ? observations.filter(o => {
            if (o.channel !== "generic") return true;
            const rec = typeof o.entity === "object" && o.entity ? o.entity : {};
            const pr = rec.properties || {};
            return Boolean(rec.source_step || pr.source_step || rec.verification_status || pr.verification_status || rec.evidence || pr.evidence || rec.context || pr.context);
          })
        : observations;
      filteredObs.forEach(observation => {
        const record = typeof observation.entity === "object" ? observation.entity : {};
        const props = record.properties || {};
        const source = record.source_step || props.source_step ||
          (Array.isArray(record.source_steps) ? record.source_steps.join(", ") : "") || "not recorded";
        appendText(provBox, "p", `${graphChannelLabel(observation.channel)} · source: ${source}`);
        const qualification = record.verification_status || props.verification_status;
        if (qualification) appendText(provBox, "p", `Recorded status: ${qualification}`);
        const context = record.evidence || props.evidence || record.context || props.context;
        if (typeof context === "string" && context.trim()) appendText(provBox, "p", context);
      });
      appendText(provBox, "p", `Scene: ${sceneId}`, "graph-evidence-id");
      row.appendChild(provBox);
      container.appendChild(row);
    });
  }

  function renderStoredRelationships(container, scene) {
    if (!container) return;
    const section = document.createElement("section");
    appendText(section, "h4", "Stored relationships");
    appendText(section, "p", "Saved graph records and review status. A stored claim is not a confirmed identity.");
    const load = document.createElement("button");
    load.className = "retro-btn-mini";
    load.textContent = "Load stored relationships";
    const rows = document.createElement("div");
    section.appendChild(load); section.appendChild(rows); container.appendChild(section);
    const videoId = state.activeVideoId, generation = state.datasetGeneration;
    load.addEventListener("click", async () => {
      load.disabled = true;
      rows.textContent = "Loading stored evidence…";
      const current = () => section.isConnected && state.activeVideoId === videoId &&
        state.datasetGeneration === generation && state.selectedSceneId === scene.id && !state.selectedEntity;
      try {
        const result = await apiGet(`/api/videos/${encodeURIComponent(videoId)}/scenes/${encodeURIComponent(scene.id)}/relationships`);
        if (!current()) return;
        rows.textContent = "";
        if (result.status !== "ok") {
          appendText(rows, "p", `Stored relationships unavailable: ${result.status || "unknown"}.`);
          return;
        }
        appendText(rows, "p", `Epoch: ${result.epoch_id}. ${result.relationships.length} stored relationships${result.truncated ? " (limit reached)" : ""}.`);
        if (result.review_ledger_available === false) appendText(rows, "p", "Review ledger unavailable; no reviewed identity can be established.");
        result.relationships.forEach(relation => {
          const detail = document.createElement("details");
          detail.className = "graph-evidence-row";
          appendText(detail, "summary", `${relation.type} · ${relation.review_status}`);
          appendText(detail, "p", `${relation.source.type}: ${relation.source.name} → ${relation.target.type}: ${relation.target.name}`, "graph-evidence-id");
          appendText(detail, "p", `Stored edge #${relation.id} · source: ${relation.evidence.provenance}`);
          if (relation.evidence.mapping_id) appendText(detail, "p", `Review mapping: ${relation.evidence.mapping_id}`);
          if (relation.evidence.reason) appendText(detail, "p", `Recorded reason: ${relation.evidence.reason}`);
          if (relation.evidence.status) appendText(detail, "p", `Recorded status: ${relation.evidence.status}`);
          (relation.evidence.selected_segments || []).forEach(turn => appendText(detail, "p", `Selected voice evidence: ${formatTime(turn.start)}–${formatTime(turn.end)}`));
          appendText(detail, "p", `Scene: ${relation.evidence.scene_id}`, "graph-evidence-id");
          const open = document.createElement("button");
          open.className = "retro-btn-mini"; open.textContent = "Open supporting scene";
          open.addEventListener("click", () => openGraphEvidence(relation.evidence.scene_id));
          detail.appendChild(open); rows.appendChild(detail);
        });
      } catch (_) {
        if (current()) rows.textContent = "Stored relationship read failed. Retry or inspect local API logs.";
      } finally {
        if (current()) load.disabled = false;
      }
    });
  }

  function renderRecordingAudio(container, evidence) {
    const section = document.createElement("section");
    section.className = "scene-audio-evidence";
    appendText(section, "h4", "Speech and speaker review");
    if (evidence.schema !== "goodq.scene_audio_view.v1") {
      appendText(section, "p", "Audio evidence version unavailable for review.");
      container.appendChild(section); return;
    }
    appendText(section, "p", "Times refer to the original recording. Players retain the whole phrase across scene cuts. Speaker tracks are unassigned; recognition and emotion accuracy remain unqualified.");
    const vocabulary = (evidence.transcription_context || {}).vocabulary;
    if (Array.isArray(vocabulary) && vocabulary.length)
      appendText(section, "p", `Name/spelling hints supplied: ${vocabulary.join(", ")}. These may bias the wording; they do not identify a speaker.`);
    (evidence.utterances || []).forEach((unit) => {
      const row = document.createElement("details");
      const bounds = unit.media_span || {};
      const time = Number.isFinite(bounds.start) && Number.isFinite(bounds.end)
        ? `${bounds.start.toFixed(2)}–${bounds.end.toFixed(2)}s · ` : "";
      const admitted = ((unit.eligibility || {}).transcript || {}).status === "eligible";
      appendText(row, "summary", `${time}${admitted ? "Model transcript" : "Possible words, unclear"}: ${unit.text || "No words resolved"}`);
      appendText(row, "p", `Speaker: ${(unit.speaker || {}).id || "unresolved"}. Confidence: not calibrated; words require listening review.`);
      const raw = (unit.confidence || {}).raw || {};
      if (Object.keys(raw).length) appendText(row, "p", `Raw decoder scores: ${JSON.stringify(raw)}. These are not probabilities that the words are correct.`);
      ["vocal_delivery", "voice_sample"].forEach((key) => {
        const admission = (unit.eligibility || {})[key] || {};
        const label = key === "voice_sample" ? "Voice signature" : "Individual vocal emotion";
        appendText(row, "p", `${label}: ${admission.status === "eligible" ? "input eligible, model result still requires review" : "withheld"}${(admission.reasons || []).length ? " · " + admission.reasons.map(r => String(r).replaceAll("_", " ")).join(", ") : ""}.`);
      });
      const review = (evidence.reviews || []).find(r => r.utterance_id === unit.id);
      if (review && /^\/api\/videos\/[^/?#]+\/scenes\/[^/?#]+\/audio-evidence\/[a-f0-9]{64}$/.test(review.url)) {
        const player = document.createElement("audio");
        player.controls = true; player.preload = "none"; player.src = review.url;
        player.setAttribute("aria-label", "Complete original speech phrase");
        player.onerror = () => appendText(row, "p", "Retained phrase audio unavailable or changed.");
        row.appendChild(player);
      }
      section.appendChild(row);
    });
    (evidence.sound_events || []).forEach(event => {
      const span = event.media_span || {};
      if (Number.isFinite(span.start) && Number.isFinite(span.end))
        appendText(section, "p", `${span.start.toFixed(2)}–${span.end.toFixed(2)}s: ${event.label} · acoustic estimate, approximate boundaries.`);
    });
    (evidence.overlap || []).forEach(event => {
      const span = event.media_span || {};
      let description = "overlap assessment unresolved";
      if (event.reason === "aligned_envelope_collision")
        description = "speech timing conflict; simultaneous voices unverified";
      else if (["collapsed_local_speaker_change", "cross_window_speaker_disagreement"].includes(event.reason))
        description = "speaker assignment unresolved";
      else if (["simultaneous_source_channels", "simultaneous_channel_observations"].includes(event.reason))
        description = "activity on multiple audio channels; speaker relationship unresolved";
      else if (event.status === "observed")
        description = "overlapping voices candidate; acoustic estimate, approximate boundaries; individual identity unresolved";
      if (Number.isFinite(span.start) && Number.isFinite(span.end))
        appendText(section, "p", `${span.start.toFixed(2)}–${span.end.toFixed(2)}s: ${description}.`);
    });
    (evidence.vocal_delivery || []).forEach(estimate => {
      appendText(section, "p", `Individual vocal delivery: ${estimate.label || "uncertain"} · uncertain model estimate, not whole-scene sentiment.`);
    });
    appendText(section, "p", evidence.voice_signature_status === "ok"
      ? "Qualified voice samples retained for review; no identity assigned."
      : evidence.voice_signature_status === "error" ? "Voice signature extraction failed; listening evidence is retained."
      : "No qualified voice signature from this scene.");
    container.appendChild(section);
  }

  // Render Metadata Detail Inspector Panel
  function renderAcousticEvidence(container, scene) {
    if (container && scene.audio_evidence) { renderRecordingAudio(container, scene.audio_evidence); return; }
    if (!container || (!scene.emotion_input && !(scene.sound_events || []).length)) return;
    const section = document.createElement("section");
    section.className = "scene-audio-evidence";
    appendText(section, "h4", "Sounds and speech estimates");
    (scene.sound_events || []).forEach((event) => {
      if (!Number.isFinite(event.start) || !Number.isFinite(event.end) || event.end <= event.start) return;
      appendText(section, "p", `${event.start.toFixed(1)}–${event.end.toFixed(1)}s: ${event.label} · sound candidate (approximate interval within scene)`);
    });
    const phrases = (scene.emotion_input || {}).phrase_selection;
    const localOverlap = ((scene.emotion_input || {}).speaker_purity || {}).local_overlap;
    if (localOverlap && localOverlap.status === "ok") {
      (Array.isArray(localOverlap.intervals) ? localOverlap.intervals : []).forEach((interval) => {
        if (!interval || !Number.isFinite(interval.start) || !Number.isFinite(interval.end) || interval.end <= interval.start) return;
        appendText(section, "p", `${interval.start.toFixed(2)}–${interval.end.toFixed(2)}s: overlapping voices · local model candidate, unreviewed; speakers unresolved`);
      });
    }
    const additionalOverlap = ((scene.emotion_input || {}).speaker_purity || {}).additional_overlap;
    if (additionalOverlap && additionalOverlap.status === "ok") {
      (Array.isArray(additionalOverlap.intervals) ? additionalOverlap.intervals : []).forEach((interval) => {
        if (!interval || !Number.isFinite(interval.start) || !Number.isFinite(interval.end) || interval.end <= interval.start) return;
        appendText(section, "p", `${interval.start.toFixed(2)}–${interval.end.toFixed(2)}s: overlapping voices · additional model candidate, unreviewed; speakers unresolved`);
      });
    } else if (additionalOverlap && ["error", "unavailable"].includes(additionalOverlap.status)) {
      appendText(section, "p", "Additional overlap assessment unavailable; individual scoring withheld.");
    }
    if (phrases && phrases.status === "insufficient_evidence") {
      appendText(section, "p", "Emotion scoring withheld: no complete, supported speech phrase. Speech may still be audible.");
    } else if (!phrases && (scene.emotion_input || {}).status === "insufficient_evidence") {
      appendText(section, "p", "Emotion estimate withheld: insufficient clear speech.");
    }
    const phraseReasons = {
      phrase_boundaries_unavailable: "phrase boundaries unavailable",
      phrase_word_timing_unavailable: "word timing unresolved",
      phrase_boundary_timing_unavailable: "phrase boundaries unresolved",
      phrase_boundary_alignment_uncertain: "phrase boundary timing uncertain",
      phrase_duration_outside_limits: "complete phrase outside supported duration; not split",
      phrase_word_evidence_mismatch: "word timing evidence disagrees",
      phrase_speakers_unresolved: "overlapping or unresolved speakers",
      local_overlap_in_phrase: "overlapping speech detected locally; individual speaker unresolved",
      additional_overlap_in_phrase: "additional overlap candidate; individual speaker unresolved",
      overlap_detection_unavailable: "overlap assessment unavailable",
      overlapping_phrase_timing_unresolved: "overlapping speakers; phrase timing unresolved",
      phrase_acoustics_uncertain_or_non_speech: "speech acoustics uncertain or a non-speech sound is present",
      phrase_speech_presence_unavailable: "speech evidence unavailable",
      phrase_speaker_boundary_unresolved: "speaker support incomplete at phrase boundary",
    };
    ((phrases || {}).rejected || []).forEach((phrase) => {
      const bounds = Number.isFinite(phrase.start) && Number.isFinite(phrase.end) && phrase.end > phrase.start
        ? `${phrase.start.toFixed(1)}–${phrase.end.toFixed(1)}s: ` : "";
      appendText(section, "p", `${bounds}${phrase.text || "Speech phrase"} · scoring withheld: ${phraseReasons[phrase.reason] || "evidence unresolved"}.`);
    });
    (scene.emotion_segments || []).forEach((segment) => {
      if (!Number.isFinite(segment.start) || !Number.isFinite(segment.end) || segment.end <= segment.start) return;
      const ranking = Object.entries(segment.scores || {})
        .filter(([, value]) => Number.isFinite(value) && value >= 0 && value <= 1)
        .sort((a, b) => b[1] - a[1]).slice(0, 3);
      const estimate = ranking.length
        ? ranking.map(([label, value]) => `${label} ${(100 * value).toFixed(0)}%`).join(", ")
        : segment.label || "unavailable";
      const qualification = segment.interpretation_status === "uncertain" ? "uncertain speech estimate" : "speech estimate";
      appendText(section, "p", `${segment.start.toFixed(1)}–${segment.end.toFixed(1)}s · ${segment.speaker}: ${estimate} · ${qualification}, unreviewed`);
      if (segment.interpretation_status === "uncertain") {
        appendText(section, "p", "Emotion uncertain: model accuracy is not qualified; candidate scores are retained for review.");
        if ((segment.uncertainty_reasons || []).includes("transcript_words_uncertain")) {
          appendText(section, "p", "Some words are uncertain; the speech phrase was kept intact.");
        }
      }
      if (ranking.length) appendText(section, "p", "These are uncalibrated model scores, not confidence in a person's feelings.");
    });
    container.appendChild(section);
  }

  function renderSpeechEvidence(container, scene) {
    if (!container) return;
    const section = document.createElement("div");
    section.className = "speech-evidence";
    appendText(section, "h4", "Speech analysis");
    const meta = scene.transcript_meta || {};
    (Array.isArray(meta.segments) ? meta.segments : []).forEach((turn) => {
      if (!turn || turn.attribution_status !== "unresolved") return;
      const reason = turn.attribution_reason === "overlapping_speakers"
        ? "Overlapping voices — speakers unresolved"
        : "Speaker attribution unresolved";
      const bounds = Number.isFinite(turn.start) && Number.isFinite(turn.end) && turn.end > turn.start
        ? `${turn.start.toFixed(1)}–${turn.end.toFixed(1)}s: ` : "";
      appendText(section, "p", `${bounds}${turn.text || "Speech"} · ${reason}.`);
    });
    const outcome = meta.error ? "runtime_failure" : scene.transcript_outcome;
    const labels = {
      transcript_available: "Transcript available",
      no_speech: "No speech detected",
      no_intelligible_speech: "Speech detected; no intelligible words returned",
      runtime_failure: "Transcription failed",
      missing_audio_artifact: "Audio artifact missing",
      low_confidence: "Low-confidence transcription",
      unclassified: "Speech outcome unclassified",
    };
    appendText(section, "p", labels[outcome] || "No speech outcome recorded (historical or unverified)");
    if (scene.transcript_outcome_reason) appendText(section, "p", `Reason: ${scene.transcript_outcome_reason}`);
    if (meta.error) appendText(section, "p", `Error: ${meta.error}`);
    const coverage = meta.transcription_decoding?.source_regions;
    if (["source_regions_v1", "source_audio_v2"].includes(coverage?.policy)) {
      const sourceAudio = coverage.policy === "source_audio_v2";
      const regionCount = sourceAudio ? coverage.recognition_region_count : coverage.detected_region_count;
      appendText(section, "p", `${coverage.completed_region_count ?? 0} of ${regionCount ?? 0} ${sourceAudio ? "original audio regions" : "detected speech regions"} processed · ${coverage.status || "unknown"}`);
      if (sourceAudio) appendText(section, "p", "Speech detection and recognition boundaries are separate. Phrase bounds and individual word times are independent model estimates.");
      appendText(section, "p", "Processing coverage does not prove that every word was recognized. Review missing or uncertain text against the source audio.");
      const regionLabels = {no_text_returned: "no text returned", rejected_no_speech_candidate: "candidate rejected as non-speech",
        text_with_unavailable_timing: "text retained without usable timing", not_attempted: "not processed", error: "processing failed"};
      const warningLabels = {compression_ratio_threshold_exceeded: "Decoder repetition warning",
        log_probability_below_threshold: "Low recognition confidence", invalid_word_timing: "Some word times unavailable",
        invalid_segment_timing: "Some recognized text has unavailable timing", word_alignment_unavailable: "Word alignment unavailable"};
      (Array.isArray(coverage.regions) ? coverage.regions : []).forEach(region => {
        const bounds = Number.isFinite(region.start) && Number.isFinite(region.end)
          ? `${region.start.toFixed(1)}–${region.end.toFixed(1)}s: ` : "";
        if (regionLabels[region.outcome]) appendText(section, "p", `${bounds}${regionLabels[region.outcome]}`);
        (Array.isArray(region.quality_flags) ? region.quality_flags : []).forEach(flag => {
          if (warningLabels[flag]) appendText(section, "p", `${bounds}${warningLabels[flag]}`);
        });
        (Array.isArray(region.unplaced_segments) ? region.unplaced_segments : []).forEach(candidate =>
          appendText(section, "p", `${candidate.text || "(empty)"} · timing unavailable`));
        if (region.timing_retry === "error") appendText(section, "p", `${bounds}Word timing recovery failed`);
      });
    }
    const detection = meta.speech_detection;
    if (detection && detection.status === "completed") {
      appendText(section, "p", `Speech detector: ${detection.method}`);
      if (typeof detection.input_duration_seconds === "number" && typeof detection.speech_duration_seconds === "number") {
        appendText(section, "p", `Audio analyzed: ${detection.input_duration_seconds.toFixed(3)} seconds; VAD speech candidates: ${detection.speech_duration_seconds.toFixed(3)} seconds`);
      }
    }
    if (meta.engine) appendText(section, "p", `Transcriber: ${meta.engine}${meta.model ? ` / ${meta.model}` : ""}`);
    const vocabulary = meta.transcription_context;
    if (vocabulary?.status === "applied" && Array.isArray(vocabulary.words)) {
      appendText(section, "p", `Vocabulary hints: ${vocabulary.words.join(", ")}`);
      appendText(section, "p", "Hints can influence recognized names; a name does not confirm who is present or speaking.");
    }
    const sampled = meta.transcription_quality?.sampled_segment_count;
    if (Number.isInteger(sampled) && sampled > 0) {
      appendText(section, "p", `Decoder retry: ${sampled} segments used sampling. Words may vary between runs; review the original audio.`);
    }
    const alignment = meta.word_alignment;
    const standaloneAudio = scene.source_kind === "audio";
    const sourceTimes = alignment?.timebase === "video_seconds";
    const hasOrigin = Number.isFinite(alignment?.source_offset_seconds) && alignment.source_offset_seconds >= 0;
    const playableTimebase = alignment?.timebase === "input_audio_seconds" || (sourceTimes && (standaloneAudio || hasOrigin));
    const phrases = Array.isArray(meta.phrase_observations)
      ? meta.phrase_observations.filter(p => p && typeof p === "object").map(p => ({text: p.text, phrase_timing: p}))
      : (Array.isArray(meta.segments) ? meta.segments : []).filter(s => s && typeof s.phrase_timing === "object" && s.phrase_timing);
    if (phrases.length) {
      const details = document.createElement("details");
      appendText(details, "summary", "Phrase timing · separate from word alignment");
      appendText(details, "p", "Whole decoder phrases may contain several sentences. Bounds are model estimates; they do not establish a single speaker or verified emotion.");
      phrases.forEach(segment => {
        const timing = segment.phrase_timing;
        const offset = timing.timebase === "video_seconds" && !standaloneAudio ? timing.source_offset_seconds : 0;
        const start = Number.isFinite(timing.start) ? timing.start - offset : null;
        const end = Number.isFinite(timing.end) ? timing.end - offset : null;
        const complete = timing.status === "model_estimated" && timing.boundary_status === "model_estimated_complete_phrase"
          && Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start;
        appendText(details, "p", complete
          ? `${start.toFixed(2)}–${end.toFixed(2)}s · ${segment.text} · estimated complete phrase`
          : `${segment.text || "(empty)"} · complete phrase boundaries unresolved`);
      });
      section.appendChild(details);
    }
    if (alignment && playableTimebase && Array.isArray(alignment.words) && alignment.words.length) {
      const details = document.createElement("details");
      appendText(details, "summary", `Word timing · ${alignment.words.length} words (model alignment, unreviewed)`);
      appendText(details, "p", `Times are relative to ${standaloneAudio ? "the original recording" : "this scene's original audio"}. Alignment does not verify the words or separate overlapping speakers.`);
      const player = standaloneAudio ? originalVideo : originalAudio;
      const audio = player.element;
      const generation = player.generation;
      alignment.words.forEach(word => {
        const recovered = word.timing_status === "recovered_model_alignment";
        const offset = sourceTimes && !standaloneAudio ? alignment.source_offset_seconds : 0;
        const start = Number.isFinite(word.start) ? word.start - offset : null;
        const end = Number.isFinite(word.end) ? word.end - offset : null;
        const valid = (word.timing_status === "aligned" || recovered) && Number.isFinite(word.start)
          && Number.isFinite(word.end) && start >= 0 && end > start;
        if (!valid) {
          appendText(details, "p", `${word.text || "(empty)"} · timing unavailable`);
          return;
        }
        const row = document.createElement("p");
        const seek = document.createElement("button");
        seek.className = "retro-btn-mini word-timing-seek";
        seek.textContent = `${start.toFixed(2)}–${end.toFixed(2)}s · ${word.text}`;
        seek.title = "Seek original audio to this model-aligned word";
        seek.disabled = !audio;
        seek.addEventListener("click", () => {
          if (audio && player.element === audio && player.generation === generation) {
            audio.currentTime = start;
          }
        });
        row.appendChild(seek);
        if (recovered) appendText(row, "span", " · recovered timing, unreviewed");
        details.appendChild(row);
      });
      section.appendChild(details);
    } else if (scene.transcript_outcome === "transcript_available") {
      appendText(section, "p", "Word timing not recorded for this transcript.");
    }
    for (const [name, status, note] of [
      ["Speaker analysis", scene.diarization_status, scene.diarization_note],
      ["Vocal emotion", scene.emotion_status, scene.emotion_note],
    ]) {
      if (!status) continue;
      const description = status === "not_applicable" && note === "no_speech_detected"
        ? "Not applicable (no speech detected)"
        : status === "success"
        ? (name === "Speaker analysis" ? "Speaker tracks recorded (unreviewed)" : "Model estimate (not verified emotion)")
        : `${status}${note ? ` (${note})` : ""}`;
      appendText(section, "p", `${name}: ${description}`);
    }
    const quality = meta.transcription_quality;
    if (quality && Array.isArray(quality.uncertain_segments) && quality.uncertain_segments.length) {
      appendText(section, "p", "Mixed speech evidence: disputed words remain in the transcript for review.");
      quality.uncertain_segments.forEach(candidate => appendText(section, "p", `Review candidate: ${candidate.text || "(empty)"}`));
    }
    if (quality && quality.status === "completed" && Array.isArray(quality.rejected_segments) && quality.rejected_segments.length) {
      appendText(section, "p", `Whisper no-speech threshold: ${quality.threshold}. Rejected candidates are retained for review, excluded from the transcript.`);
      quality.rejected_segments.forEach(candidate => {
        const probability = typeof candidate.no_speech_probability === "number" ? `${(candidate.no_speech_probability * 100).toFixed(1)}%` : "unknown";
        appendText(section, "p", `Rejected candidate (${probability} no-speech probability): ${candidate.text || "(empty)"}`);
      });
    }
    container.appendChild(section);
  }

  function renderAudioSearchEvidence(container, meta) {
    if (!container) return;
    const section = document.createElement("div");
    section.className = "audio-search-evidence";
    appendText(section, "h4", "Audio search evidence");
    if (!meta || typeof meta !== "object") {
      appendText(section, "p", "No CLAP outcome recorded for this scene.");
    } else {
      const silent = meta.status === "skipped" && meta.reason === "audio_silent";
      const label = silent ? "Silence / below energy threshold — no audio vector"
        : meta.status === "ok" ? "Audio embedding recorded" : `CLAP: ${meta.status || "unknown"}`;
      appendText(section, "p", label);
      if (meta.reason && !silent) appendText(section, "p", `Reason: ${meta.reason}`);
      if (meta.error) appendText(section, "p", `Error: ${meta.error}`);
      appendText(section, "p", meta.input_policy === "full_scene"
        ? "Input: original scene audio (speech and non-speech)"
        : "Input policy: not recorded (historical outcome)");
      const duration = meta.total_duration_s ?? meta.duration_sec;
      if (typeof duration === "number") appendText(section, "p", `Input duration: ${duration.toFixed(3)} seconds`);
      if (typeof meta.chunks_processed === "number") {
        appendText(section, "p", `Windows embedded: ${meta.chunks_processed}; quiet windows skipped: ${meta.chunks_skipped_silent || 0}`);
      }
      if (meta.status === "ok") {
        appendText(section, "p", `Vector stores: FAISS ${meta.faiss_committed === true ? "committed" : "unconfirmed"}; Qdrant ${meta.qdrant_committed === true ? "committed" : "unconfirmed"}`);
      }
      if (meta.model) appendText(section, "p", `Model: ${meta.model}`);
      if (meta.run_id) appendText(section, "p", `Ingestion run: ${meta.run_id}`);
    }
    container.appendChild(section);
  }

  function buildSceneDialogue(scene) {
    const transcript = typeof scene.transcript === "string" ? scene.transcript.trim() : "";
    if (!transcript) return [];
    const segments = scene.transcript_meta && scene.transcript_meta.segments;
    const rows = Array.isArray(segments) ? segments.filter(row =>
      row && typeof row.text === "string" && row.text.trim()).map(row => ({
        text: row.text.trim(),
        speaker: typeof row.speaker === "string" && row.speaker.trim()
          && !["?", "unknown", "unattributed"].includes(row.speaker.trim().toLowerCase())
          ? row.speaker.trim() : "Unattributed",
        start: row.start,
        end: row.end,
      })) : [];
    // Do not lose words to partial/stale metadata or infer ownership from a
    // scene-level count/dominant speaker. Retain the accepted transcript intact.
    const normalize = text => text.replace(/\s+/g, " ").trim();
    if (rows.length && normalize(rows.map(row => row.text).join(" ")) === normalize(transcript)) return rows;
    return [{ speaker: "Unattributed", text: transcript, start: scene.start, end: scene.end }];
  }

  function renderInspector() {
    resetOriginalAudio();
    resetOriginalVideo();
    ttsStop();
    const defaultMsg = document.getElementById("inspector-default-message");
    const tabsBar = document.getElementById("inspector-tabs");
    const overviewDiv = document.getElementById("inspector-details-overview");
    const entitiesDiv = document.getElementById("inspector-details-entities");
    const logsDiv = document.getElementById("inspector-details-logs");
    const transcriptZone = document.getElementById("inspector-transcript-zone");
    const subResizer = document.getElementById("resizer-subsection");
    const keyframeZone = document.getElementById("inspector-keyframe-zone");
    const keyframeActive = document.getElementById("inspector-keyframe-active");
    const keyframeImg = document.getElementById("inspector-keyframe-img");
    const keyframeTimecode = document.getElementById("inspector-keyframe-timecode");
    const keyframeNoImage = document.getElementById("inspector-keyframe-no-image");
    const noKeyframeTitle = document.getElementById("no-keyframe-title");
    const noKeyframeText = document.getElementById("no-keyframe-text");

    if (!defaultMsg) return;

    // Reset zones
    if (keyframeZone) keyframeZone.hidden = false;
    if (keyframeActive) keyframeActive.hidden = true;
    if (overviewDiv) overviewDiv.innerHTML = "";
    if (entitiesDiv) entitiesDiv.innerHTML = "";
    if (logsDiv) logsDiv.innerHTML = "";
    if (transcriptZone) {
      transcriptZone.innerHTML = "";
    }

    if (state.selectedSceneId == null && !state.selectedEntity) {
      defaultMsg.hidden = false;
      if (tabsBar) tabsBar.hidden = true;
      const contents = document.querySelectorAll(".inspector-tab-content");
      contents.forEach(c => {
        c.hidden = true;
        c.classList.remove("active-content");
      });
      if (subResizer) subResizer.style.display = "none";
      return;
    }

    defaultMsg.hidden = true;
    if (tabsBar) tabsBar.hidden = false;

    // Case 1: Active Entity Node Selection
    if (state.selectedEntity) {
      // Toggle tab buttons visibility for entity selection
      const tabOverviewBtn = document.getElementById("inspect-tab-overview");
      const tabEntitiesBtn = document.getElementById("inspect-tab-entities");
      const tabTranscriptBtn = document.getElementById("inspect-tab-transcript");
      const tabLogsBtn = document.getElementById("inspect-tab-logs");

      if (tabOverviewBtn) tabOverviewBtn.style.display = "";
      if (tabEntitiesBtn) tabEntitiesBtn.style.display = "";
      if (tabTranscriptBtn) tabTranscriptBtn.style.display = "none";
      if (tabLogsBtn) tabLogsBtn.style.display = "none";

      if (state.activeInspectorTab !== "overview" && state.activeInspectorTab !== "entities") {
        state.activeInspectorTab = "overview";
      }

      if (state.selectedSceneId != null) {
        const scene = state.scenes.find((s) => {
          if (!s) return false;
          const sId = String(s.id ?? "").trim().toLowerCase();
          const selId = String(state.selectedSceneId ?? "").trim().toLowerCase();
          return (sId && selId && sId === selId) || (s.scene_index != null && String(s.scene_index) === selId);
        });
        if (scene) {
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
          if (transcriptZone) {
            const tHeader = document.createElement("div");
            tHeader.className = "transcript-header";
            tHeader.textContent = "TRANSCRIPT LOG";
            transcriptZone.appendChild(tHeader);
            const tBody = document.createElement("div");
            tBody.className = "transcript-body";
            tBody.textContent = scene.transcript || "No transcript recorded.";
            transcriptZone.appendChild(tBody);
          }
        }
      } else {
        if (keyframeZone) keyframeZone.hidden = true;
      }
      const node = state.graph.nodes.find((n) => n.id === state.selectedEntity);
      if (!node) return;

      // List related entities (co-occurrences)
      const cooccurrences = state.graph.edges
        .filter((e) => e.source === node.id || e.target === node.id)
        .map((e) => {
          const otherId = e.source === node.id ? e.target : e.source;
          const otherNode = state.graph.nodes.find((n) => n.id === otherId);
          return {
            id: otherId,
            label: otherNode ? objectEvidenceLabel(otherNode) : otherId,
            weight: e.weight,
            type: otherNode ? otherNode.type : "generic",
            edge: e,
          };
        })
        .sort((a, b) => b.weight - a.weight);

      const header = document.createElement("div");
      header.className = "details-header";
      appendText(header, "h3", `Entity: ${objectEvidenceLabel(node)}`, "details-title");
      appendText(header, "p", `Category: ${node.type.toUpperCase()}`, "details-subtitle");
      if (overviewDiv) overviewDiv.appendChild(header);

      const countInfo = document.createElement("div");
      countInfo.className = "details-summary";
      countInfo.textContent = `Recorded in ${node.count} distinct scene${node.count === 1 ? "" : "s"}. Labels are grouped for navigation; shared scenes do not establish identity or a confirmed relationship.`;
      if (overviewDiv) overviewDiv.appendChild(countInfo);
      if (node.scopeSceneId != null && overviewDiv) appendText(overviewDiv, "p", "Anonymous label scoped to this scene; no cross-scene identity inferred.");

      if (overviewDiv) {
        const dossier = document.createElement("div");
        dossier.className = "entity-dossier-card";

        // Channel breakdown pills
        const channelCounts = { scene_present: 0, dialogue_mentioned: 0, candidate: 0, generic: 0 };
        (node.sceneIds || []).forEach(sId => {
          const obs = (node.observations || []).filter(o => o.sceneId === sId);
          const chs = [...new Set(obs.map(o => o.channel))];
          const spec = chs.filter(c => c !== "generic");
          const active = spec.length > 0 ? spec : chs;
          active.forEach(c => {
            if (channelCounts[c] !== undefined) channelCounts[c] += 1;
          });
        });
        const badgeRow = document.createElement("div");
        badgeRow.className = "entity-channel-pills";
        [
          ["scene_present", "👁 Present", channelCounts.scene_present],
          ["dialogue_mentioned", "💬 Dialogue mention", channelCounts.dialogue_mentioned],
          ["candidate", "◇ Candidate", channelCounts.candidate],
          ["generic", "🏷 Extracted only", channelCounts.generic],
        ].forEach(([chKey, chLabel, cnt]) => {
          if (!cnt) return;
          appendText(badgeRow, "span", `${chLabel}: ${cnt}`, `entity-channel-pill ch-${chKey}`);
        });
        if (badgeRow.children.length > 0) dossier.appendChild(badgeRow);

        // Timeline span & duration
        const matchedScenes = (node.sceneIds || [])
          .map(sId => state.scenes.find(s => s.id === sId))
          .filter(s => s && typeof s.start === "number" && typeof s.end === "number");
        if (matchedScenes.length > 0) {
          const minStart = Math.min(...matchedScenes.map(s => s.start));
          const maxEnd = Math.max(...matchedScenes.map(s => s.end));
          const totalSecs = Math.round(matchedScenes.reduce((acc, s) => acc + Math.max(0, s.end - s.start), 0));
          appendText(
            dossier,
            "p",
            `⏱ Timeline span: ${formatTime(minStart)} – ${formatTime(maxEnd)}  ·  ${formatTime(totalSecs)} total scene time`,
            "entity-span-row"
          );
        }

        // Top co-occurring entities quick-jump pills (prioritize people/locations over unconfirmed objects)
        if (cooccurrences.length > 0) {
          const coWrap = document.createElement("div");
          coWrap.className = "entity-top-connections";
          appendText(coWrap, "span", "🔗 Shared scenes with:", "entity-conn-label");
          const prioritizedCo = [...cooccurrences].sort((a, b) => {
            const aObj = String(a.label).includes("(unconfirmed object)") ? 1 : 0;
            const bObj = String(b.label).includes("(unconfirmed object)") ? 1 : 0;
            if (aObj !== bObj) return aObj - bObj;
            return b.weight - a.weight;
          });
          prioritizedCo.slice(0, 6).forEach(co => {
            const btn = document.createElement("button");
            btn.className = "retro-btn-mini entity-conn-pill";
            btn.textContent = `${co.label} (${co.weight})`;
            btn.addEventListener("click", (e) => {
              e.stopPropagation();
              singleSelectEntity(co.id);
            });
            coWrap.appendChild(btn);
          });
          dossier.appendChild(coWrap);
        }

        if (dossier.children.length > 0) {
          overviewDiv.appendChild(dossier);
        }
      }

      if (overviewDiv) {
        appendText(overviewDiv, "h4", "Evidence by scene");
        appendText(
          overviewDiv,
          "p",
          "💬 Dialogue mention  ·  👁 Scene presence  ·  ◇ Candidate  ·  🏷 Extracted — click any row to preview scene details.",
          "graph-evidence-legend"
        );
      }
      renderGraphEvidence(overviewDiv, node);

      if (cooccurrences.length) {
        if (entitiesDiv) appendText(entitiesDiv, "h4", "Shared-scene associations");
        const list = document.createElement("div");
        list.className = "graph-associations";
        cooccurrences.forEach((co) => {
          const relation = document.createElement("details");
          relation.className = "graph-association";
          appendText(relation, "summary", `${co.label} · ${co.weight} shared scene${co.weight === 1 ? "" : "s"}`);
          appendText(relation, "p", "Both labels occur in these scene records. Their evidence channels are listed separately.");
          const pill = document.createElement("button");
          pill.className = "retro-btn-mini";
          pill.textContent = `Explore ${co.label}`;
          pill.addEventListener("click", (e) => {
            e.stopPropagation();
            singleSelectEntity(co.id);
          });
          pill.addEventListener("dblclick", (e) => {
            e.stopPropagation();
            deselectEntity(co.id);
          });
          relation.appendChild(pill);
          renderGraphEvidence(relation, node, co.edge);
          list.appendChild(relation);
        });
        if (entitiesDiv) entitiesDiv.appendChild(list);
      } else if (entitiesDiv) {
        appendText(entitiesDiv, "p", "No shared-scene associations recorded for this label.");
      }

      switchInspectorTab(state.activeInspectorTab || "overview");
      return;
    }

    // Case 2: Active Scene Selection
    // Toggle all tab buttons visible
    const tabOverviewBtn = document.getElementById("inspect-tab-overview");
    const tabEntitiesBtn = document.getElementById("inspect-tab-entities");
    const tabTranscriptBtn = document.getElementById("inspect-tab-transcript");
    const tabLogsBtn = document.getElementById("inspect-tab-logs");

    if (tabOverviewBtn) tabOverviewBtn.style.display = "";
    if (tabEntitiesBtn) tabEntitiesBtn.style.display = "";
    if (tabTranscriptBtn) tabTranscriptBtn.style.display = "";
    if (tabLogsBtn) tabLogsBtn.style.display = "";

    let scene = state.scenes.find((s) => {
      if (!s) return false;
      const sId = String(s.id ?? "").trim().toLowerCase();
      const selId = String(state.selectedSceneId ?? "").trim().toLowerCase();
      return (sId && selId && sId === selId) || (s.scene_index != null && String(s.scene_index) === selId);
    });
    if (!scene && state.searchResults && state.searchResults.length > 0) {
      const res = state.searchResults.find((r) => {
        const rId = String(r.scene_id ?? "").trim().toLowerCase();
        const selId = String(state.selectedSceneId ?? "").trim().toLowerCase();
        return rId && selId && rId === selId;
      });
      if (res) {
        scene = {
          id: res.scene_id,
          start: res.start_time,
          end: typeof res.end_time === "number" ? res.end_time : 0.0,
          summary: res.summary || "No description available.",
          summary_meta: res.summary_meta || (res.summary
            ? {
                source: "unknown",
                provenance_status: "unknown",
                qualification: "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels).",
              }
            : {
                source: "none",
                provenance_status: "none",
                qualification: null,
              }),
          keyframe_url: resolveKeyframeUrl(res.evidence ? res.evidence.artifact_paths : null, res.source_file),
          source_kind: res.source_kind || "video",
          document_text: res.document_text || null,
          document_meta: res.document_meta || null,
          original_source_endpoint: res.original_source_endpoint,
          original_source_available: res.original_source_available === true,
          entities: Array.isArray(res.entities) ? res.entities.map(e => ({ name: e, type: "generic" })) : [],
          dialogue: buildSceneDialogue({
            transcript: res.evidence && res.evidence.transcript,
            transcript_meta: res.transcript_meta || (res.context && res.context.transcript_meta),
          }),
          transcript: (res.evidence && res.evidence.transcript) || "",
          clap_meta: res.clap_meta || (res.context && res.context.clap_meta) || null,
          transcript_meta: res.transcript_meta || (res.context && res.context.transcript_meta) || null,
          transcript_outcome: res.transcript_outcome || (res.context && res.context.transcript_outcome) || null,
          transcript_outcome_reason: res.transcript_outcome_reason || (res.context && res.context.transcript_outcome_reason) || null,
          diarization_status: res.diarization_status || null,
          diarization_note: res.diarization_note || null,
          emotion_status: res.emotion_status || null,
          emotion_note: res.emotion_note || null,
          source_file: res.source_file || "",
          original_audio_endpoint: res.original_audio_endpoint,
          original_audio_available: res.original_audio_available === true,
          original_video_endpoint: res.original_video_endpoint,
          original_video_available: res.original_video_available === true,
          sentiment_label: "NEUTRAL",
          audio_emotion: res.audio_emotion || null,
          emotion_segments: res.emotion_segments || [],
          emotion_input: res.emotion_input || null,
          sound_events: res.sound_events || [],
          audio_evidence: res.audio_evidence,
          sound_event_meta: res.sound_event_meta || null,
          content_state: "signal",
          transcript_entity_disagreements: []
        };
      }
    }
    if (!scene) return;

    if (tabTranscriptBtn && ["image", "document"].includes(scene.source_kind)) {
      tabTranscriptBtn.style.display = "none";
      if (state.activeInspectorTab === "transcript") state.activeInspectorTab = "overview";
    }

    const media = state.selectedOriginalMedia || scene;
    const staticSource = ["image", "document"].includes(scene.source_kind);
    renderOriginalAudio(media);
    renderOriginalVideo({ ...media, start: media.start ?? media.start_time });

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
        if (noKeyframeText) noKeyframeText.textContent = staticSource ? "Static source" : `TIMECODE: ${formatTime(scene.start)} - ${formatTime(scene.end)}`;
      }
    }

    if (keyframeTimecode) {
      keyframeTimecode.textContent = staticSource ? "Static source" : `${formatTime(scene.start)} - ${formatTime(scene.end)}`;
    }

    const header = document.createElement("div");
    header.className = "details-header scene-details-header";
    appendText(header, "h3", `SCENE INDEX #${scene.id}`, "details-title");
    appendText(header, "p", staticSource ? "Static source" : `Timecode: ${formatTime(scene.start)} - ${formatTime(scene.end)}`, "details-subtitle");
    if (overviewDiv) overviewDiv.appendChild(header);

    const summary = document.createElement("div");
    summary.className = "details-summary";
    summary.textContent = scene.summary || "No description available.";
    if (overviewDiv) overviewDiv.appendChild(summary);
    const inspectorQualification = (scene.summary_meta && scene.summary_meta.qualification)
      ? scene.summary_meta.qualification
      : (scene.summary && scene.summary !== "No description available.")
      ? (scene.visual_caption && scene.summary === scene.visual_caption
          ? "Summary source: visual caption (unverified model observation; not confirmed scene fact)."
          : "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels).")
      : null;
    if (inspectorQualification && overviewDiv) {
      const summaryNote = document.createElement("p");
      summaryNote.className = "summary-provenance-note";
      summaryNote.textContent = inspectorQualification;
      overviewDiv.appendChild(summaryNote);
    }

    if (typeof window !== "undefined" && typeof window.matchMedia === "function" && overviewDiv && !staticSource) {
      const quickCard = document.createElement("div");
      quickCard.className = "scene-overview-quick-card";
      const sceneSpoken = (typeof scene.transcript === "string" && scene.transcript.trim())
        ? scene.transcript.trim()
        : (Array.isArray(scene.dialogue) ? scene.dialogue.map(d => d?.text || "").filter(Boolean).join(" ").trim() : "");
      if (sceneSpoken) {
        const excerpt = sceneSpoken.length > 220
          ? `${sceneSpoken.slice(0, 218).trim()}…`
          : sceneSpoken;
        appendText(quickCard, "p", `🗣 Dialogue: "${excerpt}"`, "scene-overview-dialogue-snippet");
      }
      const quickPeople = [];
      [
        ...(scene.scene_present_entities || []),
        ...(scene.dialogue_mentioned_entities || []),
        ...(scene.candidate_visible_people || []),
      ].forEach(ent => {
        const raw = typeof ent === "string" ? ent : (ent?.name || ent?.label || ent?.text || "");
        if (raw && typeof raw === "string" && !quickPeople.includes(raw.trim())) quickPeople.push(raw.trim());
      });
      if (quickPeople.length > 0) {
        appendText(quickCard, "p", `👥 People & Mentions: ${quickPeople.slice(0, 8).join(", ")}`, "scene-overview-people-line");
      }
      if (quickCard.children.length > 0) {
        overviewDiv.appendChild(quickCard);
      }
    }

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

      let epistemicState = null;
      if (ctx_epistemic && typeof ctx_epistemic === "object") {
        epistemicState = ctx_epistemic.state || ctx_epistemic.epistemic_state || null;
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
        badge.textContent = es === "supported"
          ? "SUPPORTED (UNVERIFIED MODEL ALIGNMENT)"
          : epistemicState.replace(/_/g, " ").toUpperCase();
        badge.title = "Stored model assessment, not independently verified scene facts";
        ctxHeader.appendChild(badge);
      }

      const arb = scene.scene_context_arbitration;
      if (arb && typeof arb === "object" && arb.resolved_by) {
        const arbBadge = document.createElement("span");
        arbBadge.className = "arbitration-badge";
        arbBadge.textContent = `Arbitration basis: ${String(arb.resolved_by).replace(/_/g, " ")}`;
        arbBadge.title = arb.unresolved_axes && arb.unresolved_axes.length
          ? `Unresolved axes: ${arb.unresolved_axes.join(", ")}`
          : "No unresolved axes recorded";
        ctxHeader.appendChild(arbBadge);
      }
      ctxWrap.appendChild(ctxHeader);
      const assessmentNote = document.createElement("p");
      assessmentNote.textContent = "Stored model assessment; not verified scene facts.";
      ctxWrap.appendChild(assessmentNote);
      if (typeof ctx_llm.narrative_summary === "string" && ctx_llm.narrative_summary.trim()) {
        appendText(ctxWrap, "p", ctx_llm.narrative_summary);
      }
      if (typeof ctx_llm.emotional_arc === "string" && ctx_llm.emotional_arc.trim()) {
        appendText(ctxWrap, "p", `Tone assessment: ${ctx_llm.emotional_arc}`);
      }
      if (Array.isArray(arb?.unresolved_axes) && arb.unresolved_axes.length) {
        const unresolved = document.createElement("div");
        unresolved.textContent = `Unresolved: ${arb.unresolved_axes.join(", ")}`;
        ctxWrap.appendChild(unresolved);
      }

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
      if (!hasAnyTags && typeof ctx_llm === "string") {
        const ctxText = document.createElement("p");
        ctxText.className = "scene-context-block";
        ctxText.textContent = ctx_llm;
        ctxWrap.appendChild(ctxText);
      }
      if (overviewDiv) overviewDiv.appendChild(ctxWrap);
    }

    if (!staticSource) {
      renderSpeechEvidence(overviewDiv, scene);
      renderAudioSearchEvidence(overviewDiv, scene.clap_meta);
    }

    // Metadata grid details
    const dl = document.createElement("dl");
    dl.className = "details-metadata";
    (staticSource ? [["Source kind", scene.source_kind], ["Timing", "Static source"]] : [
      ["Duration", `${Math.round(scene.end - scene.start)} seconds`],
      ["Start Offset", `${scene.start}s`],
      ["End Offset", `${scene.end}s`],
    ]).forEach(([k, v]) => {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    if (overviewDiv) overviewDiv.appendChild(dl);

    // These are retained transcript-pattern occurrences, not acoustic detections.
    if (!staticSource && overviewDiv) {
      const cues = Array.isArray(scene.music_events) ? scene.music_events : null;
      const section = document.createElement("section");
      section.className = "music-event-cues";
      appendText(section, "h4", "Transcript music/event cues");
      appendText(section, "p", cues === null
        ? "Music/event cue evidence is not recorded for this scene."
        : cues.length ? `${cues.length} cue occurrence${cues.length === 1 ? "" : "s"} in this scene`
        : "No music/event cues retained for this scene.");
      if (cues?.length) {
        appendText(section, "p", "Transcript-pattern matches; not confirmed events or detected music.");
        const list = document.createElement("ol");
        cues.forEach(cue => {
          const record = cue && typeof cue === "object" ? cue : {};
          const row = document.createElement("li");
          row.className = "music-event-cue";
          appendText(row, "strong", typeof cue === "string" ? cue
            : record.label || record.event || record.name || record.type || record.category || "Unlabeled cue");
          if (typeof record.context === "string" && record.context) {
            appendText(row, "p", record.context);
          }
          const start = typeof record.start === "number" && Number.isFinite(record.start) ? record.start : null;
          const end = typeof record.end === "number" && Number.isFinite(record.end) ? record.end : null;
          const offset = start !== null && end !== null ? `${start}–${end} s`
            : start !== null ? `${start} s (end not recorded)`
            : end !== null ? `end ${end} s (start not recorded)` : "not recorded";
          appendText(row, "p", `Scene-relative offset: ${offset}`);
          const score = typeof record.confidence === "number" && Number.isFinite(record.confidence)
            ? `${record.confidence} (not calibrated confidence)` : "not recorded";
          appendText(row, "p", `Heuristic score: ${score}`);
          list.appendChild(row);
        });
        section.appendChild(list);
      }
      appendText(section, "p", "Execution status is not available in this view.");
      overviewDiv.appendChild(section);
    }

    // Scene entities — split into channel groups
    if (typeof window !== "undefined" && typeof window.matchMedia === "function" && entitiesDiv) {
      const banner = document.createElement("div");
      banner.className = "entities-scene-banner";
      const bannerText = (scene.summary && scene.summary !== "No description available." && scene.summary !== "No description returned.")
        ? scene.summary
        : (scene.visual_caption || (typeof scene.transcript === "string" && scene.transcript.trim() ? `"${scene.transcript.trim().slice(0, 120)}…"` : "Scene selected"));
      appendText(
        banner,
        "p",
        `🎬 ${staticSource ? "Static source" : `${formatTime(scene.start)}–${formatTime(scene.end)}`} · ${bannerText}`,
        "entities-scene-banner-text"
      );
      const jumpBtn = document.createElement("button");
      jumpBtn.className = "retro-btn-mini";
      jumpBtn.textContent = "View Scene Overview →";
      jumpBtn.addEventListener("click", () => switchInspectorTab("overview"));
      banner.appendChild(jumpBtn);
      entitiesDiv.appendChild(banner);
    }
    const scenePresent  = scene.scene_present_entities  || [];
    const mentioned     = scene.dialogue_mentioned_entities || [];
    const candidates    = scene.candidate_visible_people || [];
    const fallbackAll   = scene.entities || [];

    const renderEntityGroup = (heading, list, pillClass, enableSelect) => {
      if (!list.length) return;
      if (entitiesDiv) appendText(entitiesDiv, "h4", heading);
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
      if (entitiesDiv) entitiesDiv.appendChild(grp);
    };

    const hasChannels = scenePresent.length || mentioned.length || candidates.length;
    if (hasChannels) {
      renderEntityGroup("Scene Presence Claims", scenePresent, "scene-present", true);
      renderEntityGroup("Mentioned in Dialogue", mentioned, "mentioned", true);
      renderEntityGroup("Visibility Candidates (Unconfirmed)", candidates, "candidate-visible", true);
    } else if (fallbackAll.length) {
      if (entitiesDiv) appendText(entitiesDiv, "h4", "Detected Entities");
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
      if (entitiesDiv) entitiesDiv.appendChild(list);
    }

    // Keywords
    if (scene.keywords && scene.keywords.length > 0) {
      if (entitiesDiv) appendText(entitiesDiv, "h4", "Keywords");
      const kwRow = document.createElement("div");
      kwRow.className = "details-entities-list keywords-list";
      scene.keywords.forEach((kw) => {
        const pill = document.createElement("span");
        pill.className = "keyword-pill";
        pill.textContent = typeof kw === "string" ? kw : String(kw);
        kwRow.appendChild(pill);
      });
      if (entitiesDiv) entitiesDiv.appendChild(kwRow);
    }

    // Detected Objects
    if (scene.objects && scene.objects.length > 0) {
      if (entitiesDiv) appendText(entitiesDiv, "h4", "Detected Objects (Unconfirmed)");
      const objList = document.createElement("div");
      objList.className = "details-entities-list objects-list";
      const detailList = Array.isArray(scene.object_details) && scene.object_details.length === scene.objects.length
        ? scene.object_details
        : scene.objects.map((label) => ({ label, score: null, score_status: "unknown", source_step: "unknown", qualification: "candidate_unconfirmed" }));
      detailList.forEach((detail) => {
        const label = detail.label;
        const scoreText = typeof detail.score === "number" && Number.isFinite(detail.score)
          ? `score ${detail.score.toFixed(2)}`
          : "score unknown";
        const tsList = Array.isArray(detail.timestamps)
          ? detail.timestamps.filter((t) => typeof t === "number" && Number.isFinite(t))
          : [];
        const tsSuffix = tsList.length > 0
          ? ` @ ${tsList.map((t) => `${t.toFixed(2)}s`).join(", ")}`
          : "";
        const pill = document.createElement("span");
        pill.className = "entity-pill object-pill";
        pill.textContent = `${label} (unconfirmed, ${scoreText})${tsSuffix}`;
        pill.title = `Unconfirmed object detection: ${label} (${scoreText}${tsSuffix}; source: ${detail.source_step || "unknown"})`;
        objList.appendChild(pill);
      });
      if (entitiesDiv) entitiesDiv.appendChild(objList);
    }

    // Time Hints
    const hasTimeHints = scene.time_hints && typeof scene.time_hints === "object";
    const hasOcrDates = scene.ocr_date_candidates && scene.ocr_date_candidates.length > 0;
    if (hasTimeHints || hasOcrDates) {
      const SYSTEM_KEYS = new Set(["first_seen_ts"]);
      const hintEntries = hasTimeHints
        ? Object.entries(scene.time_hints)
            .filter(([k, v]) => !SYSTEM_KEYS.has(k) && v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length))
            .map(([k, v]) => [k.replace(/_/g, " "), Array.isArray(v) ? v.join(", ") : String(v)])
        : [];

      const dateEntries = hasOcrDates
        ? scene.ocr_date_candidates.map(d => ["ocr date", String(d)])
        : [];

      const allEntries = [...hintEntries, ...dateEntries];
      if (allEntries.length > 0) {
        if (entitiesDiv) appendText(entitiesDiv, "h4", "Time Hints");
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
        if (entitiesDiv) entitiesDiv.appendChild(hintsRow);
      }
    }

    // Conversation Dynamics
    const hasDynamics = scene.interaction_dominance || scene.conversation_owner ||
      (scene.speaker_aligned_mentions && scene.speaker_aligned_mentions.length > 0);

    if (hasDynamics) {
      if (entitiesDiv) appendText(entitiesDiv, "h4", "Conversation Dynamics");
      const dynWrap = document.createElement("div");
      dynWrap.className = "conv-dynamics-wrap";

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
      if (entitiesDiv) entitiesDiv.appendChild(dynWrap);
    }

    // Name Conflicts
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
      if (logsDiv) logsDiv.appendChild(disagSection);
    }

    // Cognitive Arbitration Details
    const arb = scene.scene_context_arbitration;
    if ((ctx_epistemic && typeof ctx_epistemic === "object") || (arb && typeof arb === "object")) {
      const cogSection = document.createElement("div");
      cogSection.className = "disag-section cognitive-section";

      const cogHeader = document.createElement("div");
      cogHeader.className = "disag-header";
      const cogTitle = document.createElement("h4");
      cogTitle.textContent = "🧠 Cognitive Arbitration";
      cogTitle.style.color = "rgba(0, 220, 200, 0.85)";
      cogTitle.style.margin = "0";
      cogHeader.appendChild(cogTitle);

      const cogToggle = document.createElement("button");
      cogToggle.className = "disag-toggle-btn";
      cogToggle.textContent = "Hide";
      cogHeader.appendChild(cogToggle);
      cogSection.appendChild(cogHeader);

      const cogBody = document.createElement("div");
      cogBody.className = "cognitive-body";
      cogBody.hidden = false;
      cogBody.style.marginTop = "8px";
      cogBody.style.fontSize = "11px";
      cogBody.style.lineHeight = "1.5";
      cogBody.style.fontFamily = "var(--font-mono)";

      if (ctx_epistemic && typeof ctx_epistemic === "object") {
        const epistemicTitle = document.createElement("div");
        epistemicTitle.style.fontWeight = "bold";
        epistemicTitle.style.color = "#00ff66";
        epistemicTitle.style.marginBottom = "4px";
        const rawEpistemicStateStr = String(ctx_epistemic.state || "unknown");
        const epistemicStateDisplay = rawEpistemicStateStr.toLowerCase() === "supported"
          ? "SUPPORTED (UNVERIFIED MODEL ALIGNMENT)"
          : rawEpistemicStateStr.toUpperCase();
        epistemicTitle.textContent = `[STORED EVIDENCE STATE: ${epistemicStateDisplay}]`;
        cogBody.appendChild(epistemicTitle);

        const epistemicGrid = document.createElement("div");
        epistemicGrid.style.display = "grid";
        epistemicGrid.style.gridTemplateColumns = "120px 1fr";
        epistemicGrid.style.gap = "4px 8px";
        epistemicGrid.style.marginBottom = "8px";
        epistemicGrid.style.paddingLeft = "8px";
        epistemicGrid.style.borderLeft = "1px solid rgba(0, 255, 102, 0.2)";

        const epistemicDetails = [
          ["Evidence Family", ctx_epistemic.evidence_family],
          ["Dominant Source", ctx_epistemic.dominant_evidence],
          ["Conflict Status", ctx_epistemic.conflict_detected === true
            || (Array.isArray(arb?.evidence_conflicts) && arb.evidence_conflicts.length)
            || (Array.isArray(arb?.unresolved_axes) && arb.unresolved_axes.length)
            ? "CONFLICTS / UNRESOLVED AXES PRESENT"
            : ctx_epistemic.conflict_detected === false ? "No conflict reported" : "Not recorded"],
        ];

        epistemicDetails.forEach(([k, v]) => {
          if (v !== undefined && v !== null) {
            const keyEl = document.createElement("span");
            keyEl.style.color = "rgba(0, 255, 102, 0.65)";
            keyEl.textContent = k + ":";
            const valEl = document.createElement("span");
            valEl.textContent = String(v);
            epistemicGrid.appendChild(keyEl);
            epistemicGrid.appendChild(valEl);
          }
        });
        cogBody.appendChild(epistemicGrid);

        const evidenceList = Array.isArray(ctx_epistemic.evidence) ? ctx_epistemic.evidence : [];
        if (evidenceList.length > 0) {
          const evHeader = document.createElement("div");
          evHeader.style.fontWeight = "bold";
          evHeader.style.color = "rgba(0, 210, 255, 0.85)";
          evHeader.style.margin = "6px 0 2px 0";
          evHeader.textContent = "Evidence Trail:";
          cogBody.appendChild(evHeader);

          const evList = document.createElement("ul");
          evList.style.margin = "0";
          evList.style.paddingLeft = "16px";
          evList.style.listStyleType = "square";
          evidenceList.forEach((ev) => {
            const li = document.createElement("li");
            const kind = ev.kind ? `[${ev.kind}] ` : "";
            const rawRole = ev.role || "";
            const isHistoricalVisualSupport = ev.kind === "visual_signal" && rawRole === "support";
            const roleLabel = isHistoricalVisualSupport ? "candidate; historical support label" : rawRole;
            const role = roleLabel ? `(${roleLabel}) ` : "";
            const kindEl = document.createElement("span");
            kindEl.style.color = "rgba(0, 210, 255, 0.7)";
            kindEl.textContent = kind;
            li.appendChild(kindEl);
            li.appendChild(document.createTextNode(role));
            const valueEl = document.createElement("strong");
            valueEl.textContent = ev.value || ev;
            li.appendChild(valueEl);
            const metaParts = [];
            if (ev.source_step) {
              metaParts.push(`source: ${ev.source_step}`);
            } else if (ev.kind === "visual_signal") {
              metaParts.push("source: unknown");
            }
            if (Array.isArray(ev.depends_on) && ev.depends_on.length) {
              metaParts.push(`depends_on: ${ev.depends_on.join("+")}`);
            }
            if (ev.source_step === "object_detect") {
              metaParts.push(
                typeof ev.score === "number" && Number.isFinite(ev.score)
                  ? `score: ${ev.score.toFixed(2)}`
                  : "score: unknown"
              );
            }
            if (metaParts.length > 0) {
              const metaEl = document.createElement("span");
              metaEl.className = "evidence-provenance-meta";
              metaEl.textContent = ` [${metaParts.join("; ")}]`;
              li.appendChild(metaEl);
            }
            evList.appendChild(li);
          });
          cogBody.appendChild(evList);
        }

        const limitsList = Array.isArray(ctx_epistemic.limits) ? ctx_epistemic.limits : [];
        if (limitsList.length > 0) {
          const limHeader = document.createElement("div");
          limHeader.style.fontWeight = "bold";
          limHeader.style.color = "rgba(255, 180, 0, 0.85)";
          limHeader.style.margin = "6px 0 2px 0";
          limHeader.textContent = "System Limits:";
          cogBody.appendChild(limHeader);

          const limList = document.createElement("ul");
          limList.style.margin = "0";
          limList.style.paddingLeft = "16px";
          limList.style.listStyleType = "square";
          limitsList.forEach((lim) => {
            const li = document.createElement("li");
            li.textContent = typeof lim === "string" ? lim : JSON.stringify(lim);
            limList.appendChild(li);
          });
          cogBody.appendChild(limList);
        }
      }

      if (arb && typeof arb === "object") {
        const arbTitle = document.createElement("div");
        arbTitle.style.fontWeight = "bold";
        arbTitle.style.color = "rgba(0, 220, 200, 0.85)";
        arbTitle.style.margin = "10px 0 4px 0";
        arbTitle.textContent = `[ARBITRATION BASIS: ${String(arb.resolved_by || "unknown").toUpperCase()}]`;
        cogBody.appendChild(arbTitle);
        if (Array.isArray(arb.unresolved_axes) && arb.unresolved_axes.length) {
          const unresolved = document.createElement("div");
          unresolved.textContent = `Unresolved axes: ${arb.unresolved_axes.join(", ")}`;
          cogBody.appendChild(unresolved);
        }

        const hyps = Array.isArray(arb.hypotheses) ? arb.hypotheses : [];
        if (hyps.length > 0) {
          const hypHeader = document.createElement("div");
          hypHeader.style.fontWeight = "bold";
          hypHeader.style.color = "rgba(0, 220, 200, 0.7)";
          hypHeader.style.margin = "4px 0 2px 0";
          hypHeader.textContent = "Hypotheses & Claims:";
          cogBody.appendChild(hypHeader);

          const hypList = document.createElement("ul");
          hypList.style.margin = "0";
          hypList.style.paddingLeft = "16px";
          hypList.style.listStyleType = "circle";
          hyps.forEach((h) => {
            const li = document.createElement("li");
            const axis = h.axis ? `[${h.axis}] ` : "";
            const family = h.evidence_family ? `via ${h.evidence_family} ` : "";
            const rawWeight = h.weight || "";
            const isHistoricalVisualSupporting = h.evidence_family === "visual" && rawWeight === "supporting";
            const weightLabel = isHistoricalVisualSupporting ? "candidate; historical supporting label" : rawWeight;
            const weight = weightLabel ? `(${weightLabel})` : "";
            const axisEl = document.createElement("span");
            axisEl.style.color = "rgba(0, 220, 200, 0.6)";
            axisEl.textContent = axis;
            li.appendChild(axisEl);
            li.appendChild(document.createTextNode(`${family}claim: `));
            const claimEl = document.createElement("strong");
            claimEl.textContent = h.claim;
            li.appendChild(claimEl);
            li.appendChild(document.createTextNode(" "));
            const weightEl = document.createElement("span");
            weightEl.style.fontStyle = "italic";
            weightEl.style.color = "rgba(255,255,255,0.5)";
            weightEl.textContent = weight;
            li.appendChild(weightEl);
            hypList.appendChild(li);
          });
          cogBody.appendChild(hypList);
        }

        const conflicts = Array.isArray(arb.evidence_conflicts) ? arb.evidence_conflicts : [];
        if (conflicts.length > 0) {
          const confHeader = document.createElement("div");
          confHeader.style.fontWeight = "bold";
          confHeader.style.color = "rgba(255, 80, 80, 0.85)";
          confHeader.style.margin = "6px 0 2px 0";
          confHeader.textContent = "Evidence Conflicts:";
          cogBody.appendChild(confHeader);

          const confList = document.createElement("ul");
          confList.style.margin = "0";
          confList.style.paddingLeft = "16px";
          confList.style.listStyleType = "square";
          conflicts.forEach((c) => {
            const li = document.createElement("li");
            li.textContent = typeof c === "string" ? c : JSON.stringify(c);
            confList.appendChild(li);
          });
          cogBody.appendChild(confList);
        }
      }

      cogToggle.addEventListener("click", () => {
        const hidden = cogBody.hidden;
        cogBody.hidden = !hidden;
        cogToggle.textContent = hidden ? "Hide" : "Show";
      });

      cogSection.appendChild(cogBody);
      if (logsDiv) logsDiv.appendChild(cogSection);
    }

    // Tags
    if (scene.tags && scene.tags.length > 0) {
      const tagsRow = document.createElement("div");
      tagsRow.className = "scene-tags-row";
      scene.tags.forEach((tag) => {
        const t = document.createElement("span");
        t.className = "scene-tag";
        t.textContent = typeof tag === "string" ? tag : (tag.label || tag.name || String(tag));
        tagsRow.appendChild(t);
      });
      if (overviewDiv) overviewDiv.appendChild(tagsRow);
    }

    renderAcousticEvidence(overviewDiv, scene);

    // Emotion + Sentiment Summary Row
    const hasEmotionData = scene.audio_emotion || (scene.audio_emotion_ranking && scene.audio_emotion_ranking.length > 0)
                        || (scene.text_emotion_ranking && scene.text_emotion_ranking.length > 0);
    if (hasEmotionData || scene.sentiment_label) {
      const emoRow = document.createElement("div");
      emoRow.className = "inspector-emo-row";

      if (scene.sentiment_label) {
        const sl = scene.sentiment_label.toLowerCase();
        const chip = document.createElement("span");
        chip.className = `sentiment-chip ${sl === "positive" ? "positive" : sl === "negative" ? "negative" : "neutral"}`;
        const score = scene.sentiment_score ?? scene.sentiment?.score;
        chip.textContent = `Text: ${sl}${Number.isFinite(score) ? ` · ${(score * 100).toFixed(1)}% score` : ""}`;
        chip.title = "Text analysis estimate; a near-even binary score is uncertain.";
        emoRow.appendChild(chip);
      }

      if (scene.audio_emotion_ranking && scene.audio_emotion_ranking.length > 0) {
        const audioHdr = document.createElement("span");
        audioHdr.className = "emo-channel-label";
        audioHdr.textContent = "Audio:";
        emoRow.appendChild(audioHdr);

        scene.audio_emotion_ranking.slice(0, 3).forEach((entry, idx) => {
          const label = entry.label || entry;
          const score = typeof entry.score === "number" ? entry.score : null;
          const eb = document.createElement("span");
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
      if (overviewDiv) overviewDiv.appendChild(emoRow);
    }

    // Visual Caption
    if (scene.visual_caption) {
      if (overviewDiv) appendText(overviewDiv, "h4", "Visual Description");
      const captionBlock = document.createElement("p");
      captionBlock.className = "visual-caption-block";
      captionBlock.textContent = scene.visual_caption;
      if (overviewDiv) overviewDiv.appendChild(captionBlock);
      const captionNote = document.createElement("p");
      captionNote.className = "visual-caption-provenance-note";
      captionNote.textContent = "Unverified model observation (image_caption); not confirmed scene fact.";
      if (overviewDiv) overviewDiv.appendChild(captionNote);
    }

    // Document text is a separate evidence channel from speech and OCR.
    if (scene.source_kind === "document" && scene.document_text) {
      const matchedResult = state.searchActive && state.searchResults.find(result =>
        String(result.scene_id) === String(scene.id) &&
        (!result.timeline_video_id || result.timeline_video_id === state.activeVideoId));
      const passage = matchedResult && matchedResult.matched_document_span;
      // Producer offsets count Unicode code points, not JavaScript UTF-16 units.
      const documentCharacters = passage ? Array.from(scene.document_text) : [];
      if (passage && Number.isInteger(passage.char_start) && Number.isInteger(passage.char_end) &&
          passage.char_start >= 0 && passage.char_end > passage.char_start &&
          passage.char_end <= documentCharacters.length &&
          typeof passage.text === "string" &&
          documentCharacters.slice(passage.char_start, passage.char_end).join("") === passage.text) {
        if (overviewDiv) appendText(overviewDiv, "h4", "Matching document passage");
        if (overviewDiv) appendText(overviewDiv, "p", `Extracted text characters ${passage.char_start}–${passage.char_end} (start inclusive, end exclusive).`);
        const passageBlock = document.createElement("pre");
        passageBlock.className = "ocr-text-block document-match-block";
        passageBlock.textContent = passage.text;
        if (overviewDiv) overviewDiv.appendChild(passageBlock);
        const context = matchedResult.document_context_span;
        if (context && Number.isInteger(context.char_start) && Number.isInteger(context.char_end) &&
            context.matched_char_start === passage.char_start && context.matched_char_end === passage.char_end &&
            context.char_start >= 0 && context.char_start <= passage.char_start &&
            context.char_end >= passage.char_end && context.char_end <= documentCharacters.length &&
            context.char_end - context.char_start <= 4096 &&
            passage.char_start - context.char_start <= 1024 && context.char_end - passage.char_end <= 1024 &&
            (context.char_start < passage.char_start || context.char_end > passage.char_end) &&
            typeof context.text === "string" &&
            documentCharacters.slice(context.char_start, context.char_end).join("") === context.text) {
          if (overviewDiv) appendText(overviewDiv, "h4", "Surrounding document context");
          if (overviewDiv) appendText(overviewDiv, "p", `Extracted text characters ${context.char_start}–${context.char_end} (start inclusive, end exclusive). Includes neighboring text around the ranked passage.`);
          const contextBlock = document.createElement("pre");
          contextBlock.className = "ocr-text-block document-context-block";
          contextBlock.textContent = context.text;
          if (overviewDiv) overviewDiv.appendChild(contextBlock);
        }
        const lexical = matchedResult.lexical_document_span;
        if (lexical && Number.isInteger(lexical.char_start) && Number.isInteger(lexical.char_end) &&
            lexical.char_start >= 0 && lexical.char_end > lexical.char_start &&
            lexical.char_end <= documentCharacters.length && lexical.char_end - lexical.char_start <= 4096 &&
            typeof lexical.text === "string" &&
            documentCharacters.slice(lexical.char_start, lexical.char_end).join("") === lexical.text) {
          if (overviewDiv) appendText(overviewDiv, "h4", "Additional lexical passage");
          if (overviewDiv) appendText(overviewDiv, "p", `Extracted text characters ${lexical.char_start}–${lexical.char_end} (start inclusive, end exclusive). Additional query-term coverage; not a generated answer.`);
          const lexicalBlock = document.createElement("pre");
          lexicalBlock.className = "ocr-text-block document-lexical-block";
          lexicalBlock.textContent = lexical.text;
          if (overviewDiv) overviewDiv.appendChild(lexicalBlock);
        }
      }
      if (overviewDiv) appendText(overviewDiv, "h4", "Document Text");
      if (scene.document_meta && scene.document_meta.text_scope === "main_document_body") {
        if (overviewDiv) appendText(overviewDiv, "p", "Main document body only. Headers, footers, notes, comments, embedded content and text in images are not extracted.");
      }
      const documentBlock = document.createElement("pre");
      documentBlock.className = "ocr-text-block document-text-block";
      documentBlock.textContent = scene.document_text;
      if (overviewDiv) overviewDiv.appendChild(documentBlock);
    }

    // OCR / Screen Text
    if (scene.ocr_text && scene.ocr_text.trim().length > 2) {
      if (overviewDiv) appendText(overviewDiv, "h4", "Screen Text (OCR)");
      const ocrBlock = document.createElement("pre");
      ocrBlock.className = "ocr-text-block";
      ocrBlock.textContent = scene.ocr_text.trim();
      if (overviewDiv) overviewDiv.appendChild(ocrBlock);
    }

    // Dialogue List
    const lines = scene.dialogue || [];
    if (lines.length) {
      const transcriptHeader = document.createElement("div");
      transcriptHeader.className = "transcript-header";
      const transcriptLabel = document.createElement("h4");
      transcriptLabel.textContent = "Scene Transcript · Synthetic voice";
      transcriptHeader.appendChild(transcriptLabel);
      appendText(transcriptHeader, "p", "Speaker labels are unreviewed model assignments within this scene, not confirmed identities. Dialogue without complete turn evidence is unattributed.", "transcript-attribution-note");

      const playAllBtn = document.createElement("button");
      playAllBtn.className = "tts-play-all-btn";
      playAllBtn.textContent = tts.supported ? "▶ READ TRANSCRIPT" : "TTS N/A";
      playAllBtn.disabled = !tts.supported;
      playAllBtn.title = "Read transcript with a synthetic voice";
      transcriptHeader.appendChild(playAllBtn);

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
        hint.textContent = "Synthetic voice reads the transcript; select text to read an excerpt.";
        container.appendChild(hint);
      }

      const rowMeta = [];
      lines.forEach((line) => {
        const row = document.createElement("div");
        row.className = "transcript-row";

        let rowBtn = null;
        if (tts.supported) {
          rowBtn = document.createElement("button");
          rowBtn.className = "tts-btn";
          rowBtn.textContent = "▶";
          rowBtn.title = "Read line with a synthetic voice";
          row.appendChild(rowBtn);
        }

        const speaker = document.createElement("strong");
        speaker.className = "transcript-speaker";
        const speakerLabel = line.speaker === "Unattributed" ? "Unattributed" : `${line.speaker} (unreviewed)`;
        speaker.textContent = `${speakerLabel}: `;
        row.appendChild(speaker);

        const textSpan = document.createElement("span");
        textSpan.className = "transcript-text";
        textSpan.textContent = line.text;
        row.appendChild(textSpan);

        container.appendChild(row);

        const speakText = `${speakerLabel}: ${line.text}`;
        rowMeta.push({ rowEl: row, rowBtn, text: speakText });

        if (rowBtn) {
          rowBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            ttsPlayRow(row, rowBtn, speakText);
          });
        }
      });

      playAllBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        ttsPlayAll(rowMeta, playAllBtn);
      });

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

      if (transcriptZone) {
        transcriptZone.innerHTML = "";
        transcriptZone.appendChild(transcriptHeader);
        transcriptZone.appendChild(container);
      }
    } else {
      if (transcriptZone) {
        transcriptZone.innerHTML = "";
        const emptyMsg = document.createElement("div");
        emptyMsg.className = "keyframe-placeholder empty-state-cyber";
        emptyMsg.style.height = "100%";
        emptyMsg.innerHTML = `
          <div class="keyframe-placeholder-crt">
            <div class="scanner-line"></div>
            <div class="empty-state-icon">📡</div>
            <div class="empty-state-title">NO TRANSCRIPT</div>
            <div class="empty-state-text">SCENE CONTAINS NO DIALOGUE OR SPEECH DATA</div>
          </div>
        `;
        transcriptZone.appendChild(emptyMsg);
      }
    }
    
    renderStoredRelationships(entitiesDiv, scene);
    switchInspectorTab(state.activeInspectorTab || "overview");
  }

  // Keep canonical names/filter IDs intact; detector labels are not confirmed facts.
  function objectEvidenceLabel(entity) {
    let text = entity.name || entity.label || "generic";
    if (entity.scopeSceneId != null) {
      text += ` · scene ${typeof entity.scopeStart === "number" ? formatTime(entity.scopeStart) : entity.scopeSceneId}`;
    }
    return (entity.entity_type || entity.type) === "object"
      ? `${text} (unconfirmed object)` : text;
  }

  // Format entity labels neatly
  function formatEntityLabel(entity) {
    if (typeof entity === "string") return entity;
    const text = entity.name || entity.label || "generic";
    if ((entity.entity_type || entity.type) === "object") return objectEvidenceLabel(entity);
    return entity.type ? `${text} (${entity.type})` : text;
  }

  // Log Data Trail events (Forensic logging)
  function logDataTrail(query, endpoint, dataset, source, reason, confidence, timeRange, rankingScore = null) {
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
      ["Ranking score (not confidence)", rankingScore],
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
  async function openSavedAppearance() {
    const params = new URLSearchParams(window.location.search);
    if (![...params.keys()].some(key => key.startsWith("watch_"))) return false;
    document.body.classList.add("people-watch");
    const banner = document.getElementById("people-watch-banner");
    const status = document.getElementById("people-watch-status");
    const back = document.getElementById("return-to-people");
    banner.hidden = false;
    const personId = params.get("watch_person"), sceneId = params.get("watch_scene");
    const videoId = params.get("watch_video"), epochId = params.get("watch_epoch");
    const matchId = params.get("watch_match"), evidenceId = params.get("watch_evidence");
    back.href = `/ui/identity_workbench/?${matchId
      ? new URLSearchParams({matches: matchId})
      : new URLSearchParams({person: personId || "", scene: sceneId || "", epoch: epochId || ""})}`;
    back.addEventListener("click", async event => {
      event.preventDefault();
      pauseOriginalAudio();
      ttsStop();
      if (originalVideo.element) originalVideo.element.pause();
      if (originalVideo.desktop && !await originalVideo.desktop.doneAndWait()) {
        status.textContent = "The desktop player could not close. Use Done, then return to your scenes.";
        return;
      }
      window.location.assign(back.href);
    });
    status.textContent = "Opening your saved scene…";
    try {
      if ((!matchId && !personId) || !sceneId || !videoId || !epochId) throw new Error("This saved-scene link is incomplete.");
      let displayName, evidenceNote;
      if (matchId) {
        const saved = await apiGet(`/api/identity/matches/${encodeURIComponent(matchId)}`);
        const matches = saved.records.filter(r => r.id === evidenceId && r.scene_id === sceneId);
        if (saved.epoch_id !== epochId || saved.video_id !== videoId || saved.applied !== false || matches.length !== 1) {
          throw new Error("This proposed match is unavailable in the active movie.");
        }
        displayName = "Proposed match";
        evidenceNote = "Identity is not applied. Review the original evidence before naming this observation.";
        back.textContent = "Back to match review";
        back.href = `/ui/identity_workbench/?${new URLSearchParams({matches: matchId, match_kind: matches[0].modality})}`;
        if (window.GoodQLibrary) back.href = window.GoodQLibrary.url(back.href);
      } else {
        const saved = await apiGet(`/api/identity/appearances/saved?person_id=${encodeURIComponent(personId)}`);
        const person = saved.people.find(p => p.id === personId);
        const matches = saved.appearances.filter(a => a.person_id === personId && a.scene_id === sceneId && a.video_id === videoId);
        if ((saved.epoch_id || matches[0]?.epoch_id) !== epochId || !person || matches.length !== 1) {
          throw new Error("This appearance is no longer available in the active movie.");
        }
        displayName = person.display_name;
        evidenceNote = "Saved appearance only; mentions and voice remain on hold.";
        back.textContent = `Back to ${person.display_name}’s scenes`;
      }
      if (!state.videos.some(v => (v.video_id || v.id) === videoId)) throw new Error("This movie is unavailable.");
      document.getElementById("dataset-select").value = videoId;
      await loadDataset(videoId);
      const scenes = state.scenes.filter(s => s.id === sceneId);
      if (state.activeVideoId !== videoId || scenes.length !== 1) throw new Error("The saved scene could not be loaded.");
      selectScene(sceneId, scenes[0]);
      status.textContent = `${displayName} · ${videoId} · ${formatTime(scenes[0].start)} – ${formatTime(scenes[0].end)}. ${evidenceNote}`;
    } catch (error) {
      status.textContent = `${error.message} Return to People and reload saved scenes.`;
    }
    return true;
  }

  async function bootRetroConsole() {
    const payload = await apiGet("/api/system/videos", "");
    state.videos = Array.isArray(payload) ? payload : (payload.videos || []);
    if (window.GoodQLibrary) window.GoodQLibrary.catalog(state.videos);

    renderVideoSelector();

    if (await openSavedAppearance()) return;

    const select = document.getElementById("dataset-select");
    const requestedSource = window.GoodQLibrary?.source;
    const requestedVideo = requestedSource && state.videos.find(v => v.library_source === requestedSource);
    if (requestedSource && !requestedVideo) {
      // An unavailable explicit source must never silently open another movie.
      if (select) select.value = "";
      return;
    }
    const activeId = requestedVideo ? requestedVideo.video_id : (select ? select.value : null);
    if (select && activeId) select.value = activeId;

    if (activeId) {
      await loadDataset(activeId);
    }
  }

  // Fetch and Load selected Video scenes
  async function loadDataset(videoId) {
    const datasetGeneration = (state.datasetGeneration || 0) + 1;
    state.datasetGeneration = datasetGeneration;
    // Invalidate responses even when a quick A -> B -> A switch returns to A.
    state.searchGeneration = (state.searchGeneration || 0) + 1;
    state.temporalSummaryGeneration = (state.temporalSummaryGeneration || 0) + 1;
    state.activeTemporalSummaryJobId = null;
    resetOriginalAudio();
    resetOriginalVideo();
    ttsStop();
    state.activeVideoId = videoId;
    
    // Toggle active ingestion / partial index badge
    const activeVideo = state.videos.find(v => (v.video_id || v.id) === videoId);
    if (activeVideo && window.GoodQLibrary) window.GoodQLibrary.select(activeVideo);
    const badge = document.getElementById("active-ingestion-badge");
    if (badge) {
      if (activeVideo && (activeVideo.source_kind || "video") === "video" && activeVideo.phase6_complete === false) {
        badge.hidden = false;
      } else {
        badge.hidden = true;
      }
    }

    state.searchResults = [];
    state.searchActive = false;
    state.lastQuery = "";
    const queryInput = document.getElementById("query-input");
    if (queryInput) queryInput.value = "";
    const searchStatus = document.getElementById("search-status");
    if (searchStatus) {
      searchStatus.textContent = "";
      searchStatus.hidden = true;
    }
    const summaryContainer = document.getElementById("narrative-summary-container");
    if (summaryContainer) summaryContainer.hidden = true;
    state.scenes = [];
    state.graph = { nodes: [], edges: [] };
    state.selectedSceneId = null;
    state.selectedEntity = null;
    state.selectedEntities = [];
    state.videoMeta = null;
    state.selectedOriginalMedia = null;
    state.intelFilter = null;   // clear any intel filter from previous dataset
    // Remove old-source content immediately, including while the new load waits.
    renderTimelineGrid();
    drawGraph();
    renderInspector();
    renderEntityFilterChecklist(false);
    renderVideoIntelPanel();

    try {
      // Fire scenes + full timeline in parallel
      const [scenesPayload, timelinePayload] = await Promise.all([
        apiGet(`/api/videos/${encodeURIComponent(videoId)}/scenes`),
        apiGet(`/api/videos/${encodeURIComponent(videoId)}/timeline/full`).catch(() => null),
      ]);
      if (state.datasetGeneration !== datasetGeneration) return;

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
        function extractDetectorScore(item) {
          if (!item || typeof item !== "object") return null;
          const props = item.properties && typeof item.properties === "object" ? item.properties : null;
          if (!props) return null;
          if (props.score_status === "unknown" || props.score_status === "not_applicable") {
            return null;
          }
          if (typeof props.detector_score === "number" && Number.isFinite(props.detector_score)) {
            return props.detector_score;
          }
          if (typeof props.raw_score === "number" && Number.isFinite(props.raw_score)) {
            return props.raw_score;
          }
          if (props.detection && typeof props.detection === "object") {
            const detScore = typeof props.detection.score === "number" && Number.isFinite(props.detection.score)
              ? props.detection.score
              : typeof props.detection.confidence === "number" && Number.isFinite(props.detection.confidence)
              ? props.detection.confidence
              : null;
            if (detScore !== null) return detScore;
          }
          if (Array.isArray(props.detections) && props.detections.length > 0) {
            const detScores = props.detections
              .map((det) => {
                if (!det || typeof det !== "object") return null;
                if (typeof det.score === "number" && Number.isFinite(det.score)) return det.score;
                if (typeof det.confidence === "number" && Number.isFinite(det.confidence)) return det.confidence;
                return null;
              })
              .filter((val) => val !== null);
            if (detScores.length > 0) return Math.max(...detScores);
            return null;
          }
          const modalities = Array.isArray(item.source_modalities) ? item.source_modalities : [];
          const steps = Array.isArray(item.source_steps) ? item.source_steps : [];
          const isVisionOnlyDetector =
            props.score_status === "observed" &&
            (props.source_step === "object_detect" || item.source_step === "object_detect") &&
            props.mention_confidence == null &&
            modalities.every((m) => m === "vision") &&
            steps.every((s) => s === "object_detect");
          if (isVisionOnlyDetector && typeof item.confidence === "number" && Number.isFinite(item.confidence)) {
            return item.confidence;
          }
          return null;
        }

        const entities = Array.isArray(scene.entities) ? scene.entities : [];
        const normalizedEntities = entities.map((item) => {
          if (typeof item === "string") {
            return {
              name: item,
              type: "generic",
              confidence: null,
              detector_score: null,
              mention_confidence: null,
              score_status: "unknown",
              source_step: null,
              verification_status: null,
              bboxes: [],
              detections: [],
              timestamps: [],
            };
          }
          const props = item.properties && typeof item.properties === "object" ? item.properties : null;
          const detectorScore = extractDetectorScore(item);
          const entityConfidence = typeof item.confidence === "number" && Number.isFinite(item.confidence)
            ? item.confidence
            : typeof item.score === "number" && Number.isFinite(item.score)
            ? item.score
            : detectorScore;
          const mentionConfidence = props && typeof props.mention_confidence === "number" && Number.isFinite(props.mention_confidence)
            ? props.mention_confidence
            : null;
          const bboxes = props && Array.isArray(props.bboxes)
            ? props.bboxes
            : props && props.bbox
            ? [props.bbox]
            : [];
          const detections = props && Array.isArray(props.detections)
            ? props.detections
            : props && props.detection
            ? [props.detection]
            : [];
          return {
            // _list_dicts() wraps raw strings as {text:"..."} — handle all key variants
            ...item,
            name: item.label || item.name || item.text || "generic",
            type: item.entity_type || item.type || item.category || "generic",
            confidence: entityConfidence,
            detector_score: detectorScore,
            mention_confidence: mentionConfidence,
            score_status: detectorScore !== null ? "observed" : "unknown",
            source_step: item.source_step || item.source || (props && props.source_step) || (Array.isArray(item.source_steps) && item.source_steps.includes("object_detect") ? "object_detect" : null),
            verification_status: (props && props.verification_status) || item.verification_status || null,
            bboxes,
            detections,
            timestamps: Array.isArray(item.timestamps) ? item.timestamps : [],
          };
        });

        // Normalize detected objects — prefer rich detected_objects when present
        const rawObjects = Array.isArray(scene.detected_objects) && scene.detected_objects.length > 0
          ? scene.detected_objects
          : (Array.isArray(scene.objects) ? scene.objects : []);
        const normalizedObjects = rawObjects.map((obj) =>
          typeof obj === "string" ? obj : (obj && (obj.label || obj.name || obj.class)) || ""
        ).filter(Boolean);
        const objectDetails = rawObjects.map((obj) => {
          if (typeof obj === "string") {
            const label = obj.trim();
            if (!label) return null;
            const matchingEntity = normalizedEntities.find(
              (ent) => ent.type === "object" && String(ent.name || "").toLowerCase() === label.toLowerCase()
            );
            const score = matchingEntity && typeof matchingEntity.detector_score === "number" && Number.isFinite(matchingEntity.detector_score)
              ? matchingEntity.detector_score
              : null;
            return {
              label,
              score,
              detector_score: score,
              mention_confidence: matchingEntity ? matchingEntity.mention_confidence : null,
              score_status: score !== null ? "observed" : "unknown",
              source_step: (matchingEntity && matchingEntity.source_step) || "unknown",
              qualification: "candidate_unconfirmed",
              bboxes: (matchingEntity && matchingEntity.bboxes) || [],
              detections: (matchingEntity && matchingEntity.detections) || [],
              timestamps: (matchingEntity && matchingEntity.timestamps) || [],
            };
          }
          if (!obj || typeof obj !== "object") return null;
          const label = String(obj.label || obj.name || obj.class || "").trim();
          if (!label) return null;
          const explicitUnknown = obj.score_status === "unknown" || obj.score_status === "not_applicable";
          const rawScore = explicitUnknown
            ? null
            : typeof obj.detector_score === "number" && Number.isFinite(obj.detector_score)
            ? obj.detector_score
            : typeof obj.raw_score === "number" && Number.isFinite(obj.raw_score)
            ? obj.raw_score
            : typeof obj.score === "number" && Number.isFinite(obj.score)
            ? obj.score
            : (obj.mention_confidence == null && obj.source_step !== "tagger" && typeof obj.confidence === "number" && Number.isFinite(obj.confidence))
            ? obj.confidence
            : null;
          const matchingEntity = normalizedEntities.find(
            (ent) => ent.type === "object" && String(ent.name || "").toLowerCase() === label.toLowerCase()
          );
          const score = explicitUnknown
            ? null
            : rawScore !== null
            ? rawScore
            : matchingEntity && typeof matchingEntity.detector_score === "number" && Number.isFinite(matchingEntity.detector_score)
            ? matchingEntity.detector_score
            : null;
          return {
            label,
            score,
            detector_score: score,
            mention_confidence: typeof obj.mention_confidence === "number" && Number.isFinite(obj.mention_confidence)
              ? obj.mention_confidence
              : (matchingEntity ? matchingEntity.mention_confidence : null),
            score_status: score !== null ? "observed" : "unknown",
            source_step: obj.source_step || obj.source || (matchingEntity && matchingEntity.source_step) || "object_detect",
            qualification: "candidate_unconfirmed",
            bboxes: Array.isArray(obj.bboxes)
              ? obj.bboxes
              : obj.bbox
              ? [obj.bbox]
              : (matchingEntity && matchingEntity.bboxes) || [],
            detections: Array.isArray(obj.detections)
              ? obj.detections
              : [obj],
            timestamps: Array.isArray(obj.timestamps)
              ? obj.timestamps
              : typeof obj.timestamp === "number" && Number.isFinite(obj.timestamp)
              ? [obj.timestamp]
              : (matchingEntity && matchingEntity.timestamps) || [],
          };
        }).filter(Boolean);

        // Top audio emotion: always normalize to string | null
        const emotionRanking = Array.isArray(scene.audio_emotion_ranking) ? scene.audio_emotion_ranking : [];

        // Safely extract a label string from any ranking entry shape
        function extractEmotionLabel(entry) {
          if (!entry) return null;
          if (typeof entry === "string") return entry;
          // {label, score}, {name, score}, {emotion, ...} etc.
          return String(entry.label || entry.name || entry.emotion || entry.category || "") || null;
        }

        // A ranked candidate is not a threshold-qualified acoustic label.
        const rawTopEmotion = scene.audio_emotion;
        // Guarantee topEmotion is always string | null — never an object
        const topEmotion = rawTopEmotion && typeof rawTopEmotion === "string" ? rawTopEmotion
          : rawTopEmotion && typeof rawTopEmotion === "object" ? extractEmotionLabel(rawTopEmotion)
          : null;

        const audioExcerpt = scene.source_kind === "audio"
          && typeof scene.transcript === "string" && scene.transcript.trim()
          ? `Transcript excerpt: ${scene.transcript.slice(0, 240)}` : null;

        const summarySource = scene.summary
          ? "explicit_summary"
          : scene.visual_caption
          ? "visual_caption"
          : audioExcerpt
          ? "transcript_excerpt"
          : scene.document_text
          ? "document_excerpt"
          : "none";
        const hasExplicitClaimProvenance = Boolean(
          scene.scene_context_llm &&
          typeof scene.scene_context_llm === "object" &&
          scene.scene_context_llm.claim_provenance &&
          typeof scene.scene_context_llm.claim_provenance === "object" &&
          scene.scene_context_llm.claim_provenance.narrative_summary
        );
        const summaryProvenanceStatus = summarySource === "explicit_summary"
          ? (hasExplicitClaimProvenance ? "observed" : "unknown")
          : summarySource === "visual_caption"
          ? (scene.caption_meta && scene.caption_meta.engine ? "observed" : "unknown")
          : summarySource === "none"
          ? "none"
          : "observed";
        const summaryMeta = {
          source: summarySource,
          provenance_status: summaryProvenanceStatus,
          qualification: summarySource === "visual_caption"
            ? "Summary source: visual caption (unverified model observation; not confirmed scene fact)."
            : summarySource === "explicit_summary"
            ? (hasExplicitClaimProvenance
                ? "Summary source: model-generated context summary (unverified; check evidence channels)."
                : "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels).")
            : summarySource === "transcript_excerpt"
            ? "Summary source: transcript excerpt (spoken dialogue only; visual presence unverified)."
            : summarySource === "document_excerpt"
            ? "Summary source: document text excerpt."
            : null,
        };
        const rawEpistemicState = scene.scene_context_epistemic && typeof scene.scene_context_epistemic === "object"
          ? (scene.scene_context_epistemic.state || scene.scene_context_epistemic.epistemic_state || null)
          : null;
        const epistemicMeta = {
          raw_state: rawEpistemicState,
          historical_supported_qualified: String(rawEpistemicState || "").toLowerCase() === "supported",
          display_state: String(rawEpistemicState || "").toLowerCase() === "supported"
            ? "SUPPORTED (UNVERIFIED MODEL ALIGNMENT)"
            : rawEpistemicState
            ? String(rawEpistemicState).toUpperCase()
            : "UNKNOWN",
        };

        return {
          id: scene.scene_id ?? scene.id,
          source_kind: scene.source_kind || "video",
          document_text: scene.document_text || null,
          document_meta: scene.document_meta || null,
          original_source_endpoint: scene.original_source_endpoint,
          original_source_available: scene.original_source_available === true,
          original_source_media_type: scene.original_source_media_type,
          start: scene.start,
          end: scene.end,
          summary: scene.summary ?? scene.visual_caption ?? audioExcerpt ?? (scene.document_text ? scene.document_text.slice(0, 240) : "No description available."),
          summary_meta: summaryMeta,
          keyframe_url: scene.representative_frame_endpoint ?? scene.representative_frame,
          original_audio_endpoint: scene.original_audio_endpoint,
          original_audio_available: scene.original_audio_available === true,
          original_video_endpoint: scene.original_video_endpoint,
          original_video_available: scene.original_video_available === true,
          entities: normalizedEntities,
          dialogue: buildSceneDialogue(scene),
          // Sprint 1 enrichment fields
          objects: normalizedObjects,
          object_details: objectDetails,
          detected_objects: Array.isArray(scene.detected_objects) ? scene.detected_objects : [],
          object_observations: Array.isArray(scene.object_observations) ? scene.object_observations : [],
          detect_meta: scene.detect_meta || null,
          visual_caption: scene.visual_caption || null,
          caption_meta: scene.caption_meta || null,
          caption_observations: Array.isArray(scene.caption_observations) ? scene.caption_observations : [],
          ocr_text: scene.ocr_text || null,
          ocr_observations: Array.isArray(scene.ocr_observations) ? scene.ocr_observations : [],
          tags: Array.isArray(scene.tags) ? scene.tags : [],
          sentiment_label: scene.sentiment_label || null,
          sentiment_score: typeof scene.sentiment_score === "number" ? scene.sentiment_score : null,
          audio_emotion: topEmotion,
          sound_events: scene.sound_events || [],
          audio_evidence: scene.audio_evidence,
          sound_event_meta: scene.sound_event_meta || null,
          emotion_segments: scene.emotion_segments || [],
          emotion_input: scene.emotion_input || null,
          clap_meta: scene.clap_meta || null,
          transcript_meta: scene.transcript_meta || null,
          transcript_outcome: scene.transcript_outcome || null,
          transcript_outcome_reason: scene.transcript_outcome_reason || null,
          diarization_status: scene.diarization_status || null,
          diarization_note: scene.diarization_note || null,
          emotion_status: scene.emotion_status || null,
          emotion_note: scene.emotion_note || null,
          audio_emotion_ranking: emotionRanking,
          content_state: scene.content_state || "signal",
          // Sprint 2: entity channels
          scene_present_entities: normalizeEntityList(scene.scene_present_entities),
          dialogue_mentioned_entities: normalizeEntityList(scene.dialogue_mentioned_entities),
          candidate_visible_people: normalizeEntityList(scene.candidate_visible_people),
          // Sprint 2: scene context
          scene_context_llm: scene.scene_context_llm || null,
          scene_context_epistemic: scene.scene_context_epistemic || null,
          epistemic_meta: epistemicMeta,
          // P0 additions: text emotion + interaction fields
          text_emotion_ranking: Array.isArray(scene.text_emotion_ranking) ? scene.text_emotion_ranking : [],
          time_hints: scene.time_hints || null,
          music_events: Array.isArray(scene.music_events) ? scene.music_events : null,
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
        null,
        ""
      );
    } catch (err) {
      if (state.datasetGeneration !== datasetGeneration) return;
      console.error("Failed to load dataset: ", err);
      logDataTrail("Error", "API fetch", videoId, "network", err.message, null, "");
    }
  }

  // ─── Sprint 3+: Video Intelligence Panel (Interactive) ────────

  // Apply an intel-driven filter to the timeline (emotion / sentiment / tag)
  function setIntelFilter(type, value, channel = null) {
    if (state.intelFilter && state.intelFilter.type === type && state.intelFilter.value === value
        && state.intelFilter.channel === channel) {
      state.intelFilter = null; // toggle off
    } else {
      state.intelFilter = { type, value, channel };
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
      const ranking = f.channel === "audio" ? scene.audio_emotion_ranking
        : f.channel === "text" ? scene.text_emotion_ranking : null;
      const top = Array.isArray(ranking) ? ranking[0] : null;
      const label = typeof top === "string" ? top : (top && typeof top.label === "string" ? top.label : "");
      return label.toLowerCase() === f.value.toLowerCase();
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
      const filterLabel = activeFilter.type === "emotion" ? `${activeFilter.channel} top-ranked emotion` : activeFilter.type;
      pill.textContent = `◆ ${filterLabel}: "${activeFilter.value}"  ×`;
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
        const rows = [
          ...textRows.filter(r => r.emotion).map(r => ({ ...r, channel: "text" })),
          ...audioRows.filter(r => r.emotion).map(r => ({ ...r, channel: "audio" })),
        ].sort((a, b) => (b.count || 0) - (a.count || 0));
        const maxCount = rows[0] ? (rows[0].count || 1) : 1;

        rows.forEach(row => {
          const isActive = activeFilter && activeFilter.type === "emotion"
            && activeFilter.channel === row.channel
            && activeFilter.value.toLowerCase() === row.emotion.toLowerCase();
          const bar = document.createElement("button");
          bar.type = "button";
          bar.className = `intel-bar-row intel-clickable${isActive ? " intel-filter-active" : ""}`;
          bar.setAttribute("aria-pressed", String(Boolean(isActive)));
          const countLabel = `${row.count} scene${row.count === 1 ? "" : "s"}`;
          bar.title = `Highlight ${countLabel} with top-ranked ${row.channel} emotion "${row.emotion}" — click to toggle`;
          const pct = Math.round(((row.count || 0) / maxCount) * 100);
          const avgScore = typeof row.average_score === "number" ? (row.average_score * 100).toFixed(0) : null;
          const channelClass = row.channel === "audio" ? "audio" : "text";

          const labelEl = document.createElement("span");
          labelEl.className = `intel-bar-label ${channelClass}`;
          labelEl.textContent = `${row.channel === "audio" ? "Audio" : "Text"}: ${row.emotion}`;
          const track = document.createElement("div");
          track.className = "intel-bar-track";
          const fill = document.createElement("div");
          fill.className = `intel-bar-fill ${channelClass}`;
          fill.style.width = `${pct}%`;
          track.appendChild(fill);
          const metaEl = document.createElement("span");
          metaEl.className = "intel-bar-meta";
          metaEl.textContent = countLabel;
          if (avgScore !== null) metaEl.title = `Average ${row.channel} model score: ${avgScore}% (not measured accuracy)`;

          bar.appendChild(labelEl);
          bar.appendChild(track);
          bar.appendChild(metaEl);
          bar.addEventListener("click", () => setIntelFilter("emotion", row.emotion, row.channel));
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
        let polText = "";
        let polTitle = "";
        if (typeof policy === "object" && policy !== null) {
          polText = `policy: ${policy.scope ? String(policy.scope).replace(/_/g, " ") : "active"}`;
          polTitle = `Audio emotion policy:\n` + Object.entries(policy).map(([k, v]) => `- ${k.replace(/_/g, " ")}: ${v}`).join("\n");
        } else {
          polText = `policy: ${String(policy).replace(/_/g, " ")}`;
          polTitle = `Audio emotion selection policy: ${policy}`;
        }
        polChip.textContent = polText;
        polChip.title = polTitle;
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
    const searchGeneration = (state.searchGeneration || 0) + 1;
    state.searchGeneration = searchGeneration;

    const searchStatus = document.getElementById("search-status");
    if (searchStatus) {
      searchStatus.textContent = "Searching…";
      searchStatus.hidden = false;
    }
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
      null,
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
      if (state.searchGeneration !== searchGeneration) return;

      const diagnosticLabels = { text: "Text", visual: "Visual", audio: "Audio" };
      const failureLabels = { unavailable: "unavailable", error: "failed", disabled: "disabled" };
      const failures = modesList.flatMap(mode => {
        const diagnostic = (searchResponse.diagnostics || {})[mode];
        const failure = diagnostic && failureLabels[diagnostic.status];
        return diagnosticLabels[mode] && failure
          ? [`${diagnosticLabels[mode]} search ${failure}.`] : [];
      });
      const passageNotices = {
        fallback: "Document passage ranking unavailable; showing the original search passages.",
        limited: "Document passage ranking covered a limited candidate set.",
      };
      const passageStatus = (searchResponse.diagnostics || {}).text_passages?.status;
      const passageNotice = modesList.includes("text") ? passageNotices[passageStatus] : null;
      if (passageNotice) failures.push(passageNotice);
      const captionStatus = (searchResponse.diagnostics || {}).visual_captions?.status;
      if (captionStatus === "fallback") {
        failures.push("Saved caption ranking unavailable; showing CLIP candidates.");
      }
      const incompleteMessage = failures.length
        ? `${modesList.length > 1 ? "Search incomplete: " : ""}${failures.join(" ")}` : "";
      if (searchStatus) {
        searchStatus.textContent = incompleteMessage;
        searchStatus.hidden = !incompleteMessage;
      }
      if (incompleteMessage) {
        logDataTrail(query, "POST /api/search/multimodal", state.activeVideoId, "search status", incompleteMessage, null, "");
      }

      // Filter grid highlighted matching scenes for active video (robust mapping check)
      const allResults = searchResponse.results || [];
      state.searchResults = allResults.filter(
        (res) => res.timeline_video_id === state.activeVideoId || res.video_id === state.activeVideoId
      );
      if (searchStatus) {
        const captionNotice = captionStatus === "ready" ? "Ranked using saved midpoint captions and CLIP." : "";
        searchStatus.textContent = [incompleteMessage, captionNotice, `${state.searchResults.length} ranked candidates for this source. Similarity does not confirm a match.`].filter(Boolean).join(" ");
        searchStatus.hidden = false;
      }
      renderTimelineGrid();

      // The selected document stays open as the query changes, but its matched
      // passage belongs to this response. Leave active audiovisual playback alone.
      if (state.scenes.some(scene => scene.source_kind === "document" &&
          String(scene.id) === String(state.selectedSceneId))) renderInspector();

      // Log matching results data trail details
      if (state.searchResults.length) {
        state.searchResults.forEach((res, i) => {
          const matchedScene = state.scenes.find((s) => {
            if (!s) return false;
            const sId = String(s.id ?? "").trim().toLowerCase();
            const rId = String(res.scene_id ?? "").trim().toLowerCase();
            return sId && rId && sId === rId;
          });
          const timeRangeStr = matchedScene ? `${formatTime(matchedScene.start)} - ${formatTime(matchedScene.end)}` : "";
          
          // Map evidence source to nice labels
          const evidenceSource = (res.modalities || res.matched_modes || ["text"])
            .map(m => m === "text" ? "text retrieval" : m === "visual" ? "keyframe" : m)
            .join(", ");

          logDataTrail(
            query,
            "POST /api/search/multimodal",
            state.activeVideoId,
            evidenceSource,
            `Ranked candidate #${i + 1}: ${res.reason || "Review the scene evidence for relevance."}`,
            res.confidence && res.confidence.overall != null ? res.confidence.overall : null,
            timeRangeStr,
            res.score
          );
        });
      } else if (!incompleteMessage) {
        logDataTrail(query, "POST /api/search/multimodal", state.activeVideoId, "search response", "No results found for active dataset.", null, "");
      }
    } catch (err) {
      if (state.searchGeneration !== searchGeneration) return;
      console.error("Search failed: ", err);
      if (searchStatus) {
        searchStatus.textContent = "Search failed. Try again.";
        searchStatus.hidden = false;
      }
      logDataTrail(query, "POST /api/search/multimodal", state.activeVideoId, "network error", err.message, null, "");
    }
  }

  // Resolve keyframe URLs for cross-tape search results
  function resolveKeyframeUrl(artifactPaths, sourceFile) {
    if (artifactPaths && artifactPaths.length > 0) {
      const pathStr = artifactPaths[0];
      const normalized = pathStr.replace(/\\/g, "/");
      const parts = normalized.split("/");
      const filename = parts[parts.length - 1]; // e.g. "scene_0000.jpg"
      if (parts.length >= 4 && parts[parts.length - 3] === "video" && parts[parts.length - 2] === "frames") {
        const videoId = parts[parts.length - 4];
        return `/api/media/video/${encodeURIComponent(videoId)}/frame/${encodeURIComponent(filename)}`;
      }
    }
    if (sourceFile) {
      const videoId = sourceFile.replace(/\.[^/.]+$/, "");
      return `/api/media/video/${encodeURIComponent(videoId)}/frame/scene_0000.jpg`;
    }
    return null;
  }

  const TEMPORAL_SUMMARY_POLL_LIMIT = 150;
  const TEMPORAL_SUMMARY_POLL_DELAY_MS = 2000;

  function isSafeTemporalSummaryScope(scope) {
    return !!scope
      && typeof scope === "object"
      && Object.keys(scope).length === 3
      && typeof scope.epoch_id === "string"
      && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/.test(scope.epoch_id)
      && typeof scope.request_sha256 === "string"
      && /^[0-9a-f]{64}$/.test(scope.request_sha256)
      && typeof scope.execution_policy_sha256 === "string"
      && /^[0-9a-f]{64}$/.test(scope.execution_policy_sha256);
  }

  function sameTemporalSummaryScope(left, right) {
    return isSafeTemporalSummaryScope(left)
      && isSafeTemporalSummaryScope(right)
      && left.epoch_id === right.epoch_id
      && left.request_sha256 === right.request_sha256
      && left.execution_policy_sha256 === right.execution_policy_sha256;
  }

  function isSafeTemporalSummaryJob(job, expectedJobId = null, expectedScope = null) {
    return !!job
      && typeof job === "object"
      && typeof job.job_id === "string"
      && /^job_[0-9a-f]{32}$/.test(job.job_id)
      && (expectedJobId === null || job.job_id === expectedJobId)
      && job.operation === "temporal_summary.generate"
      && isSafeTemporalSummaryScope(job.scope)
      && (expectedScope === null || sameTemporalSummaryScope(job.scope, expectedScope))
      && typeof job.state === "string"
      && [
        "pending_confirmation",
        "authorizing",
        "queued",
        "running",
        "succeeded",
        "failed",
        "interrupted",
        "expired"
      ].includes(job.state);
  }

  function isSafeTemporalSummaryPrepare(data, confirmationToken) {
    return !!data
      && typeof data === "object"
      && data.success === true
      && isSafeTemporalSummaryJob(data.job)
      && data.job.state === "pending_confirmation"
      && typeof confirmationToken === "string"
      && confirmationToken.trim().length > 0;
  }

  function isSafeTemporalSummaryReceipt(receipt, job, terminalState) {
    if (!receipt || typeof receipt !== "object") return false;
    const receiptKeys = Object.keys(receipt).sort();
    const expectedReceiptKeys = [
      "completed_at_utc",
      "epoch_id",
      "error_code",
      "execution_policy_sha256",
      "job_id",
      "model_evidence",
      "request_sha256",
      "result",
      "result_sha256",
      "schema",
      "started_at_utc",
      "terminal_state"
    ].sort();
    if (JSON.stringify(receiptKeys) !== JSON.stringify(expectedReceiptKeys)) return false;
    if (receipt.schema !== "goodq.temporal-summary-result.v1") return false;
    if (receipt.job_id !== job.job_id || receipt.terminal_state !== terminalState) return false;
    if (receipt.epoch_id !== job.scope.epoch_id) return false;
    if (receipt.request_sha256 !== job.scope.request_sha256) return false;
    if (receipt.execution_policy_sha256 !== job.scope.execution_policy_sha256) return false;
    if (!/^[0-9a-f]{64}$/.test(receipt.result_sha256 || "")) return false;
    if (typeof receipt.started_at_utc !== "string" || typeof receipt.completed_at_utc !== "string") return false;

    const modelEvidence = receipt.model_evidence;
    if (modelEvidence !== null) {
      if (!modelEvidence || typeof modelEvidence !== "object") return false;
      if (Object.keys(modelEvidence).sort().join(",") !== "model_id,provider") return false;
      if (typeof modelEvidence.model_id !== "string" || !modelEvidence.model_id) return false;
      if (!["ollama", "vllm"].includes(modelEvidence.provider)) return false;
    }

    if (terminalState === "failed") {
      return receipt.result === null
        && typeof receipt.error_code === "string"
        && /^[a-z0-9][a-z0-9_.-]{0,63}$/.test(receipt.error_code);
    }
    if (receipt.error_code !== null || !receipt.result || typeof receipt.result !== "object") return false;
    const result = receipt.result;
    if (
      Object.keys(result).sort().join(",")
      !== "segments,source_count,source_scene_ids,summary,truncated,warning_codes"
    ) return false;
    if (typeof result.summary !== "string" || !result.summary.trim()) return false;
    if (!Array.isArray(result.source_scene_ids) || !Array.isArray(result.segments)) return false;
    if (!Number.isInteger(result.source_count) || result.source_count !== result.source_scene_ids.length) return false;
    if (typeof result.truncated !== "boolean" || !Array.isArray(result.warning_codes)) return false;
    if (!result.warning_codes.every(code => typeof code === "string" && /^[a-z0-9][a-z0-9_.-]{0,63}$/.test(code))) return false;
    if (!result.source_scene_ids.every(sceneId => typeof sceneId === "string" && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/.test(sceneId))) return false;
    return result.segments.every(segment => {
      if (!segment || typeof segment !== "object") return false;
      if (Object.keys(segment).sort().join(",") !== "end_time,scene_id,scene_index,start_time,text") return false;
      if (!Number.isInteger(segment.scene_index) || segment.scene_index < 1 || segment.scene_index > result.source_count) return false;
      if (segment.scene_id !== result.source_scene_ids[segment.scene_index - 1]) return false;
      return typeof segment.text === "string" && !!segment.text.trim();
    });
  }

  function renderTemporalSummaryReceipt(receipt, summaryStyle, summaryBody, summaryModelBadge, auditStatus) {
    const result = receipt.result;
    summaryBody.className = "summary-body";
    if (summaryStyle === "narrative" && result.segments.length > 0) {
      summaryBody.replaceChildren();
      result.segments.forEach((segment) => {
        const span = document.createElement("span");
        span.textContent = `${segment.text} `;
        span.className = "narrative-segment clickable";
        span.setAttribute("data-scene-id", segment.scene_id);
        span.title = `Click to view Scene ${segment.scene_index}`;
        span.addEventListener("click", () => selectScene(segment.scene_id));
        summaryBody.appendChild(span);
      });
    } else {
      summaryBody.textContent = result.summary;
    }
    const modelLabel = receipt.model_evidence
      ? `${receipt.model_evidence.provider.toUpperCase()}: ${receipt.model_evidence.model_id}`
      : "NO MATCH";
    summaryModelBadge.textContent = auditStatus === "failed"
      ? `${modelLabel} / AUDIT WARNING`
      : modelLabel;
    summaryModelBadge.style.backgroundColor = auditStatus === "failed"
      ? "var(--error-color)"
      : "var(--text-color)";
  }

  function temporalSummaryDelay() {
    return new Promise(resolve => setTimeout(resolve, TEMPORAL_SUMMARY_POLL_DELAY_MS));
  }

  async function pollTemporalSummaryJob(jobId, expectedScope, summaryStyle, summaryBody, summaryModelBadge, generation) {
    if (state.temporalSummaryGeneration !== generation) return;
    state.activeTemporalSummaryJobId = jobId;
    const fetch = (path, init) => globalThis.fetch(
      typeof window !== "undefined" && window.GoodQLibrary ? window.GoodQLibrary.url(path) : path,
      init
    );
    try {
      for (let attempt = 0; attempt < TEMPORAL_SUMMARY_POLL_LIMIT; attempt += 1) {
        if (
          state.temporalSummaryGeneration !== generation
          || state.activeTemporalSummaryJobId !== jobId
        ) return;
        const response = await fetch(
          `/api/search/temporal/summarize/${encodeURIComponent(jobId)}`,
          { method: "GET" }
        );
        if (!response.ok) throw new Error("temporal_summary_status_failed");
        const data = await response.json();
        if (
          state.temporalSummaryGeneration !== generation
          || state.activeTemporalSummaryJobId !== jobId
        ) return;
        const job = data && data.job;
        if (
          !isSafeTemporalSummaryJob(job, jobId, expectedScope)
          || data.status !== job.state
        ) {
          throw new Error("temporal_summary_status_invalid");
        }
        if (["authorizing", "queued", "running"].includes(job.state)) {
          if (data.receipt !== null) throw new Error("temporal_summary_receipt_early");
          summaryModelBadge.textContent = job.state.toUpperCase();
          await temporalSummaryDelay();
          continue;
        }
        if (job.state === "succeeded") {
          if (!isSafeTemporalSummaryReceipt(data.receipt, job, "succeeded")) {
            throw new Error("temporal_summary_receipt_invalid");
          }
          if (!["recorded", "failed"].includes(job.audit_status)) {
            throw new Error("temporal_summary_audit_invalid");
          }
          renderTemporalSummaryReceipt(
            data.receipt,
            summaryStyle,
            summaryBody,
            summaryModelBadge,
            job.audit_status
          );
          return;
        }
        if (job.state === "failed") {
          if (data.receipt !== null && !isSafeTemporalSummaryReceipt(data.receipt, job, "failed")) {
            throw new Error("temporal_summary_receipt_invalid");
          }
          const code = data.receipt && data.receipt.error_code
            ? data.receipt.error_code
            : job.outcome && job.outcome.code
              ? job.outcome.code
              : "temporal_summary_failed";
          summaryBody.className = "summary-body error";
          summaryBody.textContent = `Summary failed (${code}).`;
          summaryModelBadge.textContent = job.audit_status === "failed" ? "FAILED / AUDIT WARNING" : "FAILED";
          summaryModelBadge.style.backgroundColor = "var(--error-color)";
          return;
        }
        if (job.state === "interrupted" || job.state === "expired") {
          if (data.receipt !== null) throw new Error("temporal_summary_receipt_invalid");
          summaryBody.className = "summary-body error";
          summaryBody.textContent = job.state === "interrupted"
            ? "Summary generation was interrupted. Start a new confirmed request."
            : "Summary confirmation expired. Start a new confirmed request.";
          summaryModelBadge.textContent = job.state.toUpperCase();
          summaryModelBadge.style.backgroundColor = "var(--error-color)";
          return;
        }
        throw new Error("temporal_summary_state_invalid");
      }
      throw new Error("temporal_summary_poll_timeout");
    } finally {
      if (state.activeTemporalSummaryJobId === jobId) {
        state.activeTemporalSummaryJobId = null;
      }
    }
  }

  // Execute Narrative Explorer (Temporal Reasoning) Queries
  async function executeNarrativeSearch() {
    const narrativeGeneration = state.temporalSummaryGeneration + 1;
    state.temporalSummaryGeneration = narrativeGeneration;
    state.activeTemporalSummaryJobId = null;
    const entitiesInput = document.getElementById("narrative-entities");
    const entities = entitiesInput ? entitiesInput.value.split(",").map(e => e.trim()).filter(Boolean) : [];

    const timeHintInput = document.getElementById("narrative-time-hint");
    const timeHint = timeHintInput ? timeHintInput.value.trim() : "";

    const maxResultsInput = document.getElementById("narrative-max-results");
    const maxResults = maxResultsInput ? parseInt(maxResultsInput.value) || 25 : 25;

    const styleInput = document.getElementById("narrative-style");
    const summaryStyle = styleInput ? styleInput.value : "narrative";

    const enableSummaryInput = document.getElementById("narrative-enable-summary");
    const enableSummary = enableSummaryInput ? enableSummaryInput.checked : false;

    state.lastQuery = entities.length > 0 ? entities.join(", ") : "All Scenes Sequential";
    if (timeHint) {
      state.lastQuery += ` (${timeHint})`;
    }
    state.searchActive = true;

    logDataTrail(
      state.lastQuery,
      "POST /api/search/temporal",
      state.activeVideoId,
      "user narrative search input",
      `Executing narrative search for entities: [${entities.join(", ")}], time hint: "${timeHint}"`,
      null,
      ""
    );

    // Dynamic Summary Container Handling
    const summaryContainer = document.getElementById("narrative-summary-container");
    const summaryBody = document.getElementById("narrative-summary-text");
    const summaryModelBadge = document.getElementById("summary-model-badge");

    if (summaryContainer && summaryBody && summaryModelBadge) {
      if (enableSummary) {
        summaryContainer.hidden = false;
        summaryBody.className = "summary-body loading";
        summaryBody.textContent = "Synthesizing narrative path...";
        summaryModelBadge.textContent = "THINKING";
        summaryModelBadge.style.backgroundColor = "var(--selected-color)";
      } else {
        summaryContainer.hidden = true;
      }
    }

    try {
      const searchResponse = await apiPost("/api/search/temporal", {
        entities: entities.length > 0 ? entities : null,
        time_hint: timeHint || null,
        max_results: maxResults,
        grouping: "semantic_episode"
      });
      if (state.temporalSummaryGeneration !== narrativeGeneration) return;

      state.searchResults = searchResponse.results || [];
      renderTimelineGrid();

      if (state.searchResults.length) {
        state.searchResults.forEach((res, i) => {
          const timeRangeStr = `${formatTime(res.start_time)} - ${formatTime(res.end_time)}`;
          logDataTrail(
            state.lastQuery,
            "POST /api/search/temporal",
            state.activeVideoId,
            res.source_file,
            `Narrative Scene #${i + 1}: ${res.summary || "Segment summary"} (gap: ${res.temporal_distance_from_previous}s, similarity: ${res.semantic_similarity_from_previous})`,
            null,
            timeRangeStr
          );
        });
      } else {
        logDataTrail(state.lastQuery, "POST /api/search/temporal", state.activeVideoId, "search response", "No narrative scenes returned.", null, "");
      }

      // If summarization is requested, use the governed prepare/confirm lifecycle.
      if (enableSummary && summaryContainer && summaryBody && summaryModelBadge) {
        try {
          const approved = window.confirm(
            "Generate this exact temporal summary with the approved local model policy?"
          );
          if (!approved) {
            summaryBody.className = "summary-body";
            summaryBody.textContent = "Summary generation canceled.";
            summaryModelBadge.textContent = "CANCELED";
            summaryModelBadge.style.backgroundColor = "var(--selected-color)";
            return;
          }

          const summaryRequest = {
            entities: entities.length > 0 ? entities : null,
            start_date: null,
            end_date: null,
            time_hint: timeHint || null,
            source_file: null,
            modality: null,
            max_results: maxResults,
            grouping: "semantic_episode",
            summary_style: summaryStyle
          };
          summaryBody.className = "summary-body loading";
          summaryBody.textContent = "Preparing exact temporal summary authority...";
          summaryModelBadge.textContent = "PREPARING";

          const endpoint = window.GoodQLibrary?.url("/api/search/temporal/summarize") || "/api/search/temporal/summarize";
          const prepareResponse = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "prepare", request: summaryRequest })
          });
          if (state.temporalSummaryGeneration !== narrativeGeneration) return;
          if (prepareResponse.status === 409) {
            const conflict = await prepareResponse.json();
            if (state.temporalSummaryGeneration !== narrativeGeneration) return;
            const activeJob = conflict && conflict.detail && conflict.detail.job;
            if (!isSafeTemporalSummaryJob(activeJob)) {
              throw new Error("temporal_summary_conflict_invalid");
            }
            if (["authorizing", "queued", "running"].includes(activeJob.state)) {
              await pollTemporalSummaryJob(
                activeJob.job_id,
                activeJob.scope,
                summaryStyle,
                summaryBody,
                summaryModelBadge,
                narrativeGeneration
              );
              return;
            }
            summaryBody.className = "summary-body error";
            summaryBody.textContent = "An exact summary is awaiting confirmation, but its one-time token is unavailable.";
            summaryModelBadge.textContent = "CONFIRMATION REQUIRED";
            summaryModelBadge.style.backgroundColor = "var(--error-color)";
            return;
          }
          if (!prepareResponse.ok || prepareResponse.status !== 200) {
            throw new Error("temporal_summary_prepare_failed");
          }

          const prepareData = await prepareResponse.json();
          if (state.temporalSummaryGeneration !== narrativeGeneration) return;
          let confirmationToken = prepareData && prepareData.confirmation_token;
          if (prepareData) prepareData.confirmation_token = null;
          if (!isSafeTemporalSummaryPrepare(prepareData, confirmationToken)) {
            throw new Error("temporal_summary_prepare_invalid");
          }
          const preparedJob = prepareData.job;
          const jobId = preparedJob.job_id;
          const preparedScope = preparedJob.scope;

          let confirmResponse;
          try {
            confirmResponse = await fetch(endpoint, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                action: "confirm",
                job_id: jobId,
                epoch_id: preparedScope.epoch_id,
                request_sha256: preparedScope.request_sha256,
                execution_policy_sha256: preparedScope.execution_policy_sha256,
                confirmation_token: confirmationToken,
                request: summaryRequest
              })
            });
            if (state.temporalSummaryGeneration !== narrativeGeneration) return;
          } finally {
            confirmationToken = null;
          }

          if (confirmResponse.status === 409) {
            const conflict = await confirmResponse.json();
            if (state.temporalSummaryGeneration !== narrativeGeneration) return;
            const conflictJob = conflict && conflict.detail && conflict.detail.job;
            if (!isSafeTemporalSummaryJob(conflictJob, jobId, preparedScope)) {
              throw new Error("temporal_summary_confirm_conflict_invalid");
            }
            if (["authorizing", "queued", "running"].includes(conflictJob.state)) {
              await pollTemporalSummaryJob(
                jobId,
                preparedScope,
                summaryStyle,
                summaryBody,
                summaryModelBadge,
                narrativeGeneration
              );
              return;
            }
            if (conflictJob.state === "expired" || conflictJob.state === "failed") {
              summaryBody.className = "summary-body error";
              summaryBody.textContent = conflictJob.state === "expired"
                ? "Summary confirmation expired. Start a new confirmed request."
                : "Summary authorization failed. Start a new confirmed request.";
              summaryModelBadge.textContent = conflictJob.state.toUpperCase();
              summaryModelBadge.style.backgroundColor = "var(--error-color)";
              return;
            }
            throw new Error("temporal_summary_confirm_conflict_invalid");
          }
          if (!confirmResponse.ok || confirmResponse.status !== 202) {
            throw new Error("temporal_summary_confirm_failed");
          }
          const confirmData = await confirmResponse.json();
          if (state.temporalSummaryGeneration !== narrativeGeneration) return;
          if (
            !confirmData
            || confirmData.success !== true
            || !isSafeTemporalSummaryJob(confirmData.job, jobId, preparedScope)
            || !["authorizing", "queued", "running"].includes(confirmData.job.state)
          ) {
            throw new Error("temporal_summary_confirm_invalid");
          }
          await pollTemporalSummaryJob(
            jobId,
            preparedScope,
            summaryStyle,
            summaryBody,
            summaryModelBadge,
            narrativeGeneration
          );
        } catch (sumErr) {
          if (state.temporalSummaryGeneration !== narrativeGeneration) return;
          console.error("Narrative summarization failed: ", sumErr);
          summaryBody.className = "summary-body error";
          summaryBody.textContent = "Summary request could not be verified. Try again.";
          summaryModelBadge.textContent = "ERROR";
          summaryModelBadge.style.backgroundColor = "var(--error-color)";
        }
      }
    } catch (err) {
      if (state.temporalSummaryGeneration !== narrativeGeneration) return;
      console.error("Narrative search failed: ", err);
      logDataTrail(state.lastQuery, "POST /api/search/temporal", state.activeVideoId, "network error", err.message, null, "");
      if (summaryBody && summaryModelBadge && enableSummary) {
        summaryBody.className = "summary-body";
        summaryBody.innerHTML = `<span style="color: var(--error-color)">⚠ SEARCH ERROR</span>: ${err.message}`;
        summaryModelBadge.textContent = "ERROR";
        summaryModelBadge.style.backgroundColor = "var(--error-color)";
      }
    }
  }

  // Accessibility Controls & Event Listeners
  function initAccessibility() {
    const screen = document.getElementById("crt-screen");
    const toggleSfx = document.getElementById("toggle-sfx");
    const toggleIntel = document.getElementById("toggle-intel-btn");
    const intelPanel = document.getElementById("video-intel-panel");
    const toggleDroppad = document.getElementById("toggle-droppad-btn");
    const droppadPanel = document.getElementById("droppad-panel");

    if (!screen || !toggleSfx) return;

    // Load initial Retro SFX state from localStorage
    const storedSfx = localStorage.getItem("goodq-retro-sfx");
    if (storedSfx === "off") {
      screen.classList.add("no-sfx");
      toggleSfx.textContent = "Retro SFX: OFF";
      toggleSfx.classList.add("btn-disabled");
    } else {
      screen.classList.remove("no-sfx");
      toggleSfx.textContent = "Retro SFX: ON";
      toggleSfx.classList.remove("btn-disabled");
    }

    // Theme toggle handler (NIGHT / DAY / AUTO)
    const toggleTheme = document.getElementById("toggle-theme");
    if (toggleTheme) {
      const themes = ["night", "day", "auto"];
      let currentTheme = localStorage.getItem("goodq-theme") || "night";

      function applyTheme(theme) {
        currentTheme = theme;
        localStorage.setItem("goodq-theme", theme);
        
        try {
          window.matchMedia("(prefers-color-scheme: dark)").removeEventListener("change", handleSystemThemeChange);
        } catch (e) {
          try {
            window.matchMedia("(prefers-color-scheme: dark)").removeListener(handleSystemThemeChange);
          } catch (e2) {}
        }

        if (theme === "night") {
          document.body.classList.remove("theme-day");
          toggleTheme.textContent = "Theme: NIGHT";
          toggleTheme.title = "Current: Night Mode (Deep Obsidian). Click to change.";
        } else if (theme === "day") {
          document.body.classList.add("theme-day");
          toggleTheme.textContent = "Theme: DAY";
          toggleTheme.title = "Current: Day Mode (Daylight Studio). Click to change.";
        } else if (theme === "auto") {
          toggleTheme.textContent = "Theme: AUTO";
          toggleTheme.title = "Current: Auto Mode (System theme). Click to change.";
          const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
          if (isDark) {
            document.body.classList.remove("theme-day");
          } else {
            document.body.classList.add("theme-day");
          }
          try {
            window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", handleSystemThemeChange);
          } catch (e) {
            try {
              window.matchMedia("(prefers-color-scheme: dark)").addListener(handleSystemThemeChange);
            } catch (e2) {}
          }
        }
        if (typeof drawGraph === "function") {
          drawGraph();
        }
      }

      function handleSystemThemeChange(e) {
        if (currentTheme === "auto") {
          if (e.matches) {
            document.body.classList.remove("theme-day");
          } else {
            document.body.classList.add("theme-day");
          }
          if (typeof drawGraph === "function") {
            drawGraph();
          }
        }
      }

      applyTheme(currentTheme);

      toggleTheme.addEventListener("click", () => {
        const nextIndex = (themes.indexOf(currentTheme) + 1) % themes.length;
        applyTheme(themes[nextIndex]);
      });
    }

    // Intel panel toggle
    const ribbonIntel = document.getElementById("ribbon-toggle-intel");
    const closeIntel = document.getElementById("close-intel-btn");
    function setIntelVisibility(visible) {
      state.intelVisible = Boolean(visible);
      if (intelPanel) intelPanel.hidden = !state.intelVisible;
      const resizerIntel = document.getElementById("resizer-intel");
      if (resizerIntel) resizerIntel.hidden = !state.intelVisible;
      if (toggleIntel) {
        toggleIntel.textContent = state.intelVisible ? "Intel: ON" : "Intel: OFF";
        toggleIntel.classList.toggle("intel-active", state.intelVisible);
      }
      if (ribbonIntel) {
        ribbonIntel.classList.toggle("pane-active", state.intelVisible);
        ribbonIntel.setAttribute("aria-pressed", String(state.intelVisible));
      }
      if (state.intelVisible && state.videoMeta) renderVideoIntelPanel();
      resizeCanvas();
    }
    if (toggleIntel && intelPanel) {
      toggleIntel.addEventListener("click", () => setIntelVisibility(!state.intelVisible));
    }
    if (ribbonIntel && intelPanel) {
      ribbonIntel.addEventListener("click", () => setIntelVisibility(!state.intelVisible));
    }
    if (closeIntel && intelPanel) {
      closeIntel.addEventListener("click", () => setIntelVisibility(false));
    }

    // Drop Pad Panel toggle & drag handlers
    let dropZoneInitialized = false;
    function initDropZoneHandlers() {
      if (dropZoneInitialized) return;
      const dropZone = document.getElementById("drop-zone");
      const fileInput = document.getElementById("droppad-file-input");
      const uploadStatus = document.getElementById("upload-status");
      if (!dropZone || !fileInput) return;

      // Prevent default drag/drop behaviors on window level to avoid accidental page navigation/redirects
      window.addEventListener("dragover", (e) => {
        e.preventDefault();
      }, false);
      window.addEventListener("drop", (e) => {
        e.preventDefault();
      }, false);

      dropZone.addEventListener("click", (e) => {
        if (e.target.closest("#upload-status")) return;
        fileInput.click();
      });

      fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
          handleUpload(fileInput.files[0]);
        }
      });

      ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropZone.classList.add("dragover");
        }, false);
      });

      ["dragleave", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropZone.classList.remove("dragover");
        }, false);
      });

      dropZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
          handleUpload(files[0]);
        }
      }, false);

      async function handleUpload(file) {
        if (!file) return;
        const supportedExts = [
          ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v",
          ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma",
          ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp",
          ".pdf", ".txt", ".md", ".doc", ".docx"
        ];
        const ext = "." + file.name.split(".").pop().toLowerCase();
        if (!supportedExts.includes(ext)) {
          showStatus(`[ERROR] Unsupported file format: ${ext}`, true);
          return;
        }

        showStatus(`[REQUEST] Preparing governed staging for ${file.name}...`, false);
        const formData = new FormData();
        formData.append("file", file);
        formData.append("action", "prepare");
        formData.append("policy_profile", "local_ingest_facade_v1");

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/ingest/submit", true);

        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            showStatus(`[UPLOADING] ${file.name} (${percent}%)`, false);
          }
        });

        xhr.addEventListener("load", async () => {
          if (xhr.status !== 201 && xhr.status !== 200) {
            try {
              const resp = JSON.parse(xhr.responseText);
              showStatus(`[ERROR] ${resp.detail || "Upload failed"}`, true);
            } catch {
              showStatus(`[ERROR] Upload failed with code ${xhr.status}`, true);
            }
            return;
          }

          const prepared = JSON.parse(xhr.responseText);
          if (prepared.status === "duplicate") {
            showStatus(
              `[DUPLICATE] Already processed${prepared.duplicate_of_run_id ? ` in ${prepared.duplicate_of_run_id}` : ""}.`,
              false
            );
            fileInput.value = "";
            return;
          }
          const hashPrefix = (prepared.file_sha256 || "").slice(0, 12);
          showStatus(
            `[WAITING] Awaiting confirmation: ${prepared.request_id}. No Watchdog visibility yet.`,
            false
          );
          const approved = window.confirm(
            `Stage this exact file for Watchdog?\n\n` +
            `Name: ${prepared.original_name}\n` +
            `Size: ${prepared.size_bytes} bytes\n` +
            `SHA-256: ${hashPrefix}...\n` +
            `Request: ${prepared.request_id}`
          );
          const transitionPayload = approved
            ? {
                action: "confirm",
                request_id: prepared.request_id,
                confirmation_token: prepared.confirmation_token
              }
            : {
                action: "cancel",
                request_id: prepared.request_id,
                confirmation_token: prepared.confirmation_token
              };
          try {
            const transitionResponse = await fetch("/api/ingest/submit", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(transitionPayload)
            });
            const transition = await transitionResponse.json();
            if (!transitionResponse.ok) {
              throw new Error(transition.detail || `HTTP ${transitionResponse.status}`);
            }
            if (!approved) {
              showStatus(`[CANCELED] Prepared request ${prepared.request_id} removed.`, false);
              fileInput.value = "";
              return;
            }

            showStatus(
              `[OK] Request staged: ${transition.request_id}. Waiting for Watchdog pickup.`,
              false
            );
            fileInput.value = "";
            setTimeout(() => {
              state.droppadVisible = false;
              if (droppadPanel) droppadPanel.hidden = true;
              if (toggleDroppad) toggleDroppad.classList.remove("droppad-active");
              uploadStatus.hidden = true;
            }, 4000);
          } catch (err) {
            showStatus(`[ERROR] Staging decision failed: ${err.message}`, true);
          }
        });

        xhr.addEventListener("error", () => {
          showStatus(`[ERROR] Network upload error occurred.`, true);
        });

        xhr.send(formData);
      }

      function showStatus(msg, isError) {
        if (!uploadStatus) return;
        uploadStatus.hidden = false;
        uploadStatus.textContent = msg;
        uploadStatus.classList.toggle("error", isError);
      }

      dropZoneInitialized = true;
    }

    const ribbonStage = document.getElementById("ribbon-toggle-stage");
    const closeDroppad = document.getElementById("close-droppad-btn");
    function setDroppadVisibility(visible) {
      state.droppadVisible = Boolean(visible);
      if (droppadPanel) droppadPanel.hidden = !state.droppadVisible;
      if (toggleDroppad) toggleDroppad.classList.toggle("droppad-active", state.droppadVisible);
      if (ribbonStage) {
        ribbonStage.classList.toggle("pane-active", state.droppadVisible);
        ribbonStage.setAttribute("aria-pressed", String(state.droppadVisible));
      }
      if (state.droppadVisible) {
        initDropZoneHandlers();
      }
    }
    if (toggleDroppad && droppadPanel) {
      toggleDroppad.addEventListener("click", () => setDroppadVisibility(!state.droppadVisible));
    }
    if (ribbonStage && droppadPanel) {
      ribbonStage.addEventListener("click", () => setDroppadVisibility(!state.droppadVisible));
    }
    if (closeDroppad && droppadPanel) {
      closeDroppad.addEventListener("click", () => setDroppadVisibility(false));
    }

    toggleSfx.addEventListener("click", () => {
      const active = screen.classList.toggle("no-sfx");
      toggleSfx.textContent = active ? "Retro SFX: OFF" : "Retro SFX: ON";
      toggleSfx.classList.toggle("btn-disabled", active);
      localStorage.setItem("goodq-retro-sfx", active ? "off" : "on");
      drawGraph(); // Redraw canvas graph to toggle node glows
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

    const ribbonSearch = document.getElementById("ribbon-toggle-search");
    const ribbonInspector = document.getElementById("ribbon-toggle-inspector");
    const ribbonTimeline = document.getElementById("ribbon-toggle-timeline");

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
      if (ribbonSearch) {
        ribbonSearch.classList.toggle("pane-active", !layoutState.leftCollapsed);
        ribbonSearch.setAttribute("aria-pressed", String(!layoutState.leftCollapsed));
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
      if (ribbonInspector) {
        ribbonInspector.classList.toggle("pane-active", !layoutState.rightCollapsed);
        ribbonInspector.setAttribute("aria-pressed", String(!layoutState.rightCollapsed));
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
      if (ribbonTimeline) {
        ribbonTimeline.classList.toggle("pane-active", !layoutState.bottomCollapsed);
        ribbonTimeline.setAttribute("aria-pressed", String(!layoutState.bottomCollapsed));
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

    if (ribbonSearch) {
      ribbonSearch.addEventListener("click", () => {
        if (layoutState.leftCollapsed) {
          layoutState.leftWidth = layoutState.lastLeftWidth;
          layoutState.leftCollapsed = false;
        } else {
          layoutState.lastLeftWidth = layoutState.leftWidth;
          layoutState.leftCollapsed = true;
        }
        applyLayout();
      });
    }

    if (ribbonInspector) {
      ribbonInspector.addEventListener("click", () => {
        if (layoutState.rightCollapsed) {
          layoutState.rightWidth = layoutState.lastRightWidth;
          layoutState.rightCollapsed = false;
        } else {
          layoutState.lastRightWidth = layoutState.rightWidth;
          layoutState.rightCollapsed = true;
        }
        applyLayout();
      });
    }

    if (ribbonTimeline) {
      ribbonTimeline.addEventListener("click", () => {
        if (layoutState.bottomCollapsed) {
          layoutState.bottomHeight = layoutState.lastBottomHeight;
          layoutState.bottomCollapsed = false;
        } else {
          layoutState.lastBottomHeight = layoutState.bottomHeight;
          layoutState.bottomCollapsed = true;
        }
        applyLayout();
      });
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
    const inspectorDetails = document.getElementById("inspector-details-logs");
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
        dataTrailSection.classList.add("resizing");

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
          dataTrailSection.classList.remove("resizing");
        }

        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup", stopResizing);
      });
    }
  }

  // Initialize Inspector tab buttons
  function initInspectorTabs() {
    const tabs = ["overview", "transcript", "entities", "logs"];
    tabs.forEach(tabName => {
      const btn = document.getElementById(`inspect-tab-${tabName}`);
      if (btn) {
        btn.addEventListener("click", () => {
          switchInspectorTab(tabName);
        });
      }
    });
  }

  function switchInspectorTab(tabName) {
    state.activeInspectorTab = tabName;

    const tabs = ["overview", "transcript", "entities", "logs"];
    tabs.forEach(name => {
      const btn = document.getElementById(`inspect-tab-${name}`);
      const content = document.getElementById(`inspector-content-${name}`);
      
      if (btn) {
        if (name === tabName) {
          btn.classList.add("active");
        } else {
          btn.classList.remove("active");
        }
      }

      if (content) {
        content.hidden = (name !== tabName);
        if (name === tabName) {
          content.classList.add("active-content");
        } else {
          content.classList.remove("active-content");
        }
      }
    });

    // Handle subsection resizer display based on Collapsed state in logs tab
    if (tabName === "logs") {
      const dataTrailSection = document.getElementById("data-trail-section");
      const subResizer = document.getElementById("resizer-subsection");
      if (subResizer) {
        const isCollapsed = dataTrailSection && dataTrailSection.classList.contains("collapsed");
        subResizer.style.display = isCollapsed ? "none" : "";
      }
    }
  }

  // Obsidian & God's Eye View Progressive Disclosure & Quick-Filter Enhancements
  function initModernWorkspaceEnhancements() {
    const overviewEl = document.getElementById("inspector-details-overview");
    const transcriptEl = document.getElementById("inspector-transcript-zone");
    const entitiesEl = document.getElementById("inspector-details-entities");
    const logsEl = document.getElementById("inspector-details-logs");
    const dataTrailList = document.getElementById("data-trail-list");
    const toggleDiagBtn = document.getElementById("toggle-diagnostics-btn");

    // 1. Progressive Disclosure for Diagnostic Cards in Overview
    if (overviewEl) {
      overviewEl.addEventListener("click", (e) => {
        if (e.target.closest("button, a, summary, input, select")) return;
        const card = e.target.closest(".speech-evidence, .audio-search-evidence, .music-event-cues");
        if (card) {
          card.classList.toggle("is-expanded");
        }
      });

      overviewEl.addEventListener("beforematch", (e) => {
        const card = e.target.closest(".speech-evidence, .audio-search-evidence, .music-event-cues");
        if (card) {
          card.classList.add("is-expanded");
        }
      });
    }

    if (toggleDiagBtn && overviewEl) {
      toggleDiagBtn.addEventListener("click", () => {
        const expanded = overviewEl.classList.toggle("diagnostics-expanded");
        toggleDiagBtn.setAttribute("aria-pressed", String(expanded));
        toggleDiagBtn.textContent = expanded ? "Diagnostics: Expanded" : "Diagnostics: Compact";
      });
    }

    // 2. Inspector Tab Count Badges (via data-badge so button.textContent remains exact)
    function updateInspectorTabBadges() {
      const tabTranscript = document.getElementById("inspect-tab-transcript");
      const tabEntities = document.getElementById("inspect-tab-entities");
      const tabLogs = document.getElementById("inspect-tab-logs");

      if (tabTranscript && transcriptEl) {
        const rows = transcriptEl.querySelectorAll(".transcript-row").length;
        if (rows > 0) tabTranscript.setAttribute("data-badge", String(rows));
        else tabTranscript.removeAttribute("data-badge");
      }

      if (tabEntities && entitiesEl) {
        const items = entitiesEl.querySelectorAll(".entity-item, .graph-evidence-row, li").length;
        if (items > 0) tabEntities.setAttribute("data-badge", String(items));
        else tabEntities.removeAttribute("data-badge");
      }

      if (tabLogs) {
        const trailItems = dataTrailList ? dataTrailList.querySelectorAll(".log-item").length : 0;
        if (trailItems > 0) tabLogs.setAttribute("data-badge", String(trailItems));
        else tabLogs.removeAttribute("data-badge");
      }
    }

    if (typeof MutationObserver !== "undefined") {
      const inspectorObserver = new MutationObserver(() => updateInspectorTabBadges());
      [transcriptEl, entitiesEl, logsEl, dataTrailList].forEach((el) => {
        if (el) inspectorObserver.observe(el, { childList: true, subtree: true });
      });
      updateInspectorTabBadges();
    }

    // 3. Entity Filter Quick Search & Clear Button
    const entityFilterInput = document.getElementById("entity-quick-filter");
    const clearEntityBtn = document.getElementById("clear-entity-filter-btn");
    const entityListEl = document.getElementById("entity-filter-list");

    function applyEntityQuickFilter() {
      if (!entityListEl) return;
      const q = (entityFilterInput ? entityFilterInput.value : "").trim().toLowerCase();
      const items = entityListEl.querySelectorAll(".entity-filter-item");
      items.forEach((item) => {
        const txt = (item.textContent || "").toLowerCase();
        item.hidden = q.length > 0 && !txt.includes(q);
      });
      if (clearEntityBtn) {
        const hasSelection = Array.isArray(state.selectedEntities) && state.selectedEntities.length > 0;
        clearEntityBtn.hidden = !(hasSelection || q.length > 0);
      }
    }

    if (entityFilterInput) {
      entityFilterInput.addEventListener("input", applyEntityQuickFilter);
    }
    if (clearEntityBtn) {
      clearEntityBtn.addEventListener("click", () => {
        if (entityFilterInput) entityFilterInput.value = "";
        resetEntityFilters();
        applyEntityQuickFilter();
      });
    }
    if (typeof MutationObserver !== "undefined" && entityListEl) {
      const entityObserver = new MutationObserver(() => applyEntityQuickFilter());
      entityObserver.observe(entityListEl, { childList: true });
    }

    // 4. Caption grounding markup is removed by the API for every consumer
    //    (api.main.GroundingMarkupMiddleware); no client-side rewriting here.

    // 5. Timeline Quick Filter, Scene Count Badge & Grid/Compact View Toggle
    const timelineFilterInput = document.getElementById("timeline-quick-filter");
    const timelineCountBadge = document.getElementById("timeline-count-badge");
    const timelineGridEl = document.getElementById("timeline-grid");
    const viewGridBtn = document.getElementById("timeline-view-grid");
    const viewCompactBtn = document.getElementById("timeline-view-compact");

    function updateTimelineQuickFilterAndBadge() {
      if (!timelineGridEl) return;
      const q = (timelineFilterInput ? timelineFilterInput.value : "").trim().toLowerCase();
      const cards = timelineGridEl.querySelectorAll(".scene-card");
      let visibleCount = 0;
      cards.forEach((card) => {
        const txt = (card.textContent || "").toLowerCase();
        const match = q.length === 0 || txt.includes(q);
        card.style.display = match ? "" : "none";
        if (match) visibleCount += 1;
      });
      if (timelineCountBadge) {
        const total = cards.length;
        timelineCountBadge.textContent = q.length > 0
          ? `${visibleCount} / ${total} scenes`
          : `${total} scene${total === 1 ? "" : "s"}`;
      }
    }

    if (timelineFilterInput) {
      timelineFilterInput.addEventListener("input", updateTimelineQuickFilterAndBadge);
    }
    if (typeof MutationObserver !== "undefined" && timelineGridEl) {
      const timelineObserver = new MutationObserver(() => updateTimelineQuickFilterAndBadge());
      timelineObserver.observe(timelineGridEl, { childList: true });
      updateTimelineQuickFilterAndBadge();
    }

    if (viewGridBtn && viewCompactBtn && timelineGridEl) {
      viewGridBtn.addEventListener("click", () => {
        timelineGridEl.classList.remove("compact-view");
        viewGridBtn.classList.add("active");
        viewGridBtn.setAttribute("aria-pressed", "true");
        viewCompactBtn.classList.remove("active");
        viewCompactBtn.setAttribute("aria-pressed", "false");
      });
      viewCompactBtn.addEventListener("click", () => {
        timelineGridEl.classList.add("compact-view");
        viewCompactBtn.classList.add("active");
        viewCompactBtn.setAttribute("aria-pressed", "true");
        viewGridBtn.classList.remove("active");
        viewGridBtn.setAttribute("aria-pressed", "false");
      });
    }

    // 6. Keyboard Shortcuts: '/' focuses Search Input, 'Escape' clears active quick filter
    document.addEventListener("keydown", (e) => {
      const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : "";
      const isEditing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (e.target && e.target.isContentEditable);
      if (e.key === "/" && !isEditing && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const qInput = document.getElementById("query-input");
        if (qInput) {
          e.preventDefault();
          qInput.focus();
          qInput.select();
        }
      } else if (e.key === "Escape" && isEditing) {
        if (e.target === timelineFilterInput && timelineFilterInput.value) {
          timelineFilterInput.value = "";
          updateTimelineQuickFilterAndBadge();
        } else if (e.target === entityFilterInput && entityFilterInput.value) {
          entityFilterInput.value = "";
          applyEntityQuickFilter();
        }
        e.target.blur();
      }
    });
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
      } else {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const hoverHit = state.graph.nodes.find((node) => {
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
        const nextHoverId = hoverHit ? hoverHit.id : null;
        if (state.hoveredNodeId !== nextHoverId) {
          state.hoveredNodeId = nextHoverId;
          canvas.style.cursor = nextHoverId ? "pointer" : "";
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
      if (state.hoveredNodeId) {
        state.hoveredNodeId = null;
        canvas.style.cursor = "";
        drawGraph();
      }
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
  let pollingTimeoutId = null;
  let currentPollInterval = 3000;
  let manuallyDismissedRunId = null;

  function startStatusPolling() {
    pollStatus();
  }

  async function pollStatus() {
    let shouldContinuePolling = true;
    try {
      const statusPayload = await apiGet("/api/status") || {};
      const processing = statusPayload.processing || {};
      const cliProgress = processing.cli_progress || {};
      const isActive = cliProgress.active === true;
      const isFailed = cliProgress.status === "failed";
      const wsl = statusPayload.wsl || {};
      const isWslFrozen = wsl.status === "frozen" || wsl.audio_processing === "unresponsive";

      // Update adaptive polling interval based on active state
      currentPollInterval = isActive ? 1500 : 3000;

      // Extract GPU details defensively
      const gpu = statusPayload.gpu || {};
      const gpuUtil = gpu.gpu_utilization !== undefined ? gpu.gpu_utilization : "unknown";
      const gpuMemUsed = gpu.gpu_memory_used !== undefined ? Math.round(gpu.gpu_memory_used / 1024 * 10) / 10 : "unknown";
      const gpuMemTotal = gpu.gpu_memory_total !== undefined ? Math.round(gpu.gpu_memory_total / 1024 * 10) / 10 : "unknown";
      const telemetryStr = `[GPU: ${gpuUtil}% | VRAM: ${gpuMemUsed}GB/${gpuMemTotal}GB]`;

      // Update header fingerprint
      const fingerprintEl = document.getElementById("header-fingerprint");
      const runId = cliProgress.run_id || (processing.cli_progress && processing.cli_progress.run_id) || processing.run_id || "None";
      if (fingerprintEl) {
        const db = statusPayload.database || {};
        const epoch = db.epoch || "N/A";
        fingerprintEl.textContent = `Epoch: ${epoch} | Run: ${runId}`;
        if (typeof window !== "undefined" && window.GoodQLibrary?.caption) {
          fingerprintEl.textContent = window.GoodQLibrary.caption;
          fingerprintEl.title = `Selected collection: ${epoch}; run: ${runId}`;
        }
      }

      const progressWidget = document.getElementById("ingestion-progress-widget");
      const headerStatus = document.querySelector(".header-status");
      const currentFile = cliProgress.current_video || processing.current_video || "unknown";
      const stage = cliProgress.stage || "ingestion";
      const sceneEl = document.getElementById("progress-scene-count");
      if ((isActive || isFailed) && sceneEl) {
        const extension = String(currentFile).split(".").pop().toLowerCase();
        if (["jpg", "jpeg", "png", "bmp", "gif", "tiff", "webp"].includes(extension)) {
          sceneEl.textContent = "Source: image";
        } else if (["pdf", "txt", "md", "doc", "docx"].includes(extension)) {
          sceneEl.textContent = "Source: document";
        } else {
          const sceneIndex = cliProgress.scene_index || 0;
          const scenesTotal = cliProgress.scenes_total || "?";
          sceneEl.textContent = stage === "Processing additional scenes..." || scenesTotal === "..." || sceneIndex === "..."
            ? "Analyzing..." : `Scene: ${sceneIndex} of ${scenesTotal}`;
        }
      }

      // Handle WSL Frozen Header Status
      if (headerStatus) {
        if (isWslFrozen) {
          headerStatus.classList.add("wsl-frozen");
          headerStatus.textContent = `Status: WSL FROZEN ${telemetryStr}`;
        } else {
          headerStatus.classList.remove("wsl-frozen");
          if (isActive) {
            const pct = cliProgress.progress_percent !== undefined ? cliProgress.progress_percent : (processing.progress_percent || 0);
            headerStatus.textContent = `Status: INGESTING (${pct}%) ${telemetryStr}`;
          } else {
            headerStatus.textContent = `Status: ONLINE ${telemetryStr}`;
          }
        }
      }

      if (isActive) {
        // Reset manual dismissal and failed state when active
        if (manuallyDismissedRunId === runId) {
          manuallyDismissedRunId = null;
        }

        if (!wasIngesting) {
          wasIngesting = true;
          ingestionStartTime = Date.now();
          if (progressWidget) {
            progressWidget.hidden = false;
            progressWidget.classList.remove("failed-state");
            const titleEl = progressWidget.querySelector(".progress-title");
            if (titleEl) titleEl.textContent = "🛰 PIPELINE INGESTION ACTIVE";
          }
          const closeBtn = document.getElementById("progress-close-btn");
          if (closeBtn) closeBtn.style.display = "none";
          if (headerStatus) {
            headerStatus.classList.add("ingesting");
          }
        }

        const pct = cliProgress.progress_percent !== undefined ? cliProgress.progress_percent : (processing.progress_percent || 0);
        const currentStep = cliProgress.current_step || "processing";

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

        const elapsedSec = Math.floor((Date.now() - ingestionStartTime) / 1000);
        const elapsedEl = document.getElementById("progress-elapsed");
        if (elapsedEl) elapsedEl.textContent = `Elapsed: ${elapsedSec}s`;
      } else if (isFailed) {
        wasIngesting = false;
        if (headerStatus) {
          headerStatus.classList.remove("ingesting");
        }
        if (progressWidget && manuallyDismissedRunId !== runId) {
          progressWidget.hidden = false;
          progressWidget.classList.add("failed-state");
          const titleEl = progressWidget.querySelector(".progress-title");
          if (titleEl) titleEl.textContent = "🛰 PIPELINE INGESTION FAILED";

          const pct = cliProgress.progress_percent !== undefined ? cliProgress.progress_percent : (processing.progress_percent || 0);

          const fileEl = document.getElementById("progress-file");
          if (fileEl) fileEl.textContent = `File: ${currentFile}`;

          const barFill = document.getElementById("progress-bar-fill");
          if (barFill) barFill.style.width = `${pct}%`;

          const textEl = document.getElementById("progress-text");
          if (textEl) textEl.textContent = `${pct}%`;

          const stepEl = document.getElementById("progress-step");
          if (stepEl) stepEl.textContent = "Step: FAILED - check local processing logs for details";

          const stageEl = document.getElementById("progress-stage");
          if (stageEl) stageEl.textContent = `Stage: ${stage}`;

          const closeBtn = document.getElementById("progress-close-btn");
          if (closeBtn) {
            closeBtn.style.display = "inline-block";
            closeBtn.onclick = async () => {
              manuallyDismissedRunId = runId;
              progressWidget.hidden = true;
              await bootRetroConsole();
            };
          }
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

          // Wait 3 seconds then hide and reload dataset
          setTimeout(async () => {
            if (progressWidget) progressWidget.hidden = true;
            if (headerStatus) {
              headerStatus.classList.remove("ingesting");
            }
            // Trigger boot loader to refresh dropdown and grid
            await bootRetroConsole();
          }, 3000);
        } else {
          // Normal idle state, make sure widget is hidden and status is normal
          if (progressWidget && !progressWidget.hidden) {
            progressWidget.hidden = true;
          }
          if (headerStatus) {
            if (headerStatus.classList.contains("ingesting")) {
              headerStatus.classList.remove("ingesting");
            }
          }
        }
      }
    } catch (err) {
      if (err && err.status === 403) {
        shouldContinuePolling = false;
        const headerStatus = document.querySelector(".header-status");
        if (headerStatus) {
          headerStatus.classList.remove("wsl-frozen", "ingesting");
          headerStatus.textContent = "Status: LAN READ-ONLY — operator telemetry requires loopback";
        }
        console.info("Status polling disabled: operator telemetry is restricted to loopback.");
      } else {
        console.warn("Status polling error: ", err);
        currentPollInterval = 3000;
      }
    } finally {
      if (pollingTimeoutId) clearTimeout(pollingTimeoutId);
      if (shouldContinuePolling) {
        pollingTimeoutId = setTimeout(pollStatus, currentPollInterval);
      } else {
        pollingTimeoutId = null;
      }
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bootRetroConsole()
      .then(() => {
        initAccessibility();
        initLayoutControls();
        initCanvasControls();
        initTTS();
        initInspectorTabs();
        initModernWorkspaceEnhancements();
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

        // Tab switching controls
        const tabMultimodal = document.getElementById("tab-multimodal");
        const tabNarrative = document.getElementById("tab-narrative");
        const searchForm = document.getElementById("search-form");
        const narrativeForm = document.getElementById("narrative-form");
        const tabHelperMsg = document.getElementById("tab-helper-msg");

        if (tabMultimodal && tabNarrative && searchForm && narrativeForm) {
          tabMultimodal.addEventListener("click", () => {
            tabMultimodal.classList.add("active");
            tabNarrative.classList.remove("active");
            searchForm.hidden = false;
            narrativeForm.hidden = true;
            state.activeSearchTab = "multimodal";
            if (tabHelperMsg) {
              tabHelperMsg.textContent = "Search for specific moments using natural language. Fits video content, speech transcripts, and visual elements.";
              tabHelperMsg.style.borderColor = "var(--border-color)";
            }
            resetAllFilters();
          });

          tabNarrative.addEventListener("click", () => {
            tabNarrative.classList.add("active");
            tabMultimodal.classList.remove("active");
            searchForm.hidden = true;
            narrativeForm.hidden = false;
            state.activeSearchTab = "narrative";
            if (tabHelperMsg) {
              tabHelperMsg.textContent = "Synthesize a chronological history/briefing of events based on target people/places and temporal hints.";
              tabHelperMsg.style.borderColor = "var(--border-selected)";
            }
            resetAllFilters();
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

        // Narrative Form Submission
        const narrForm = document.getElementById("narrative-form");
        if (narrForm) {
          narrForm.addEventListener("submit", (e) => {
            e.preventDefault();
            executeNarrativeSearch();
          });
        }

        // Narrative summary close button
        const closeSummaryBtn = document.getElementById("close-summary-btn");
        if (closeSummaryBtn) {
          closeSummaryBtn.addEventListener("click", () => {
            const summaryContainer = document.getElementById("narrative-summary-container");
            if (summaryContainer) {
              summaryContainer.hidden = true;
            }
          });
        }

        // Modality Mode selector buttons mapping
        const modeButtons = document.querySelectorAll(".mode-btn");
        modeButtons.forEach((btn) => {
          btn.addEventListener("click", () => {
            const currentMode = btn.getAttribute("data-mode");
            
            if (currentMode === "identity") {
              state.modes = new Set(["identity"]);
            } else if (currentMode === "all") {
              state.modes = new Set(["text", "visual", "audio"]);
            } else {
              state.modes.delete("identity");
              if (state.modes.has(currentMode)) {
                // A query needs at least one evidence source.
                if (state.modes.size > 1) state.modes.delete(currentMode);
              } else {
                state.modes.add(currentMode);
              }
            }
            modeButtons.forEach((button) => {
              const mode = button.getAttribute("data-mode");
              const active = mode === "all" ? state.modes.size === 3 : state.modes.has(mode);
              button.classList.toggle("active", active);
              button.setAttribute("aria-pressed", String(active));
            });
          });
        });
      })
      .catch((err) => {
        console.error("Bootloader failed: ", err);
        const select = document.getElementById("dataset-select");
        if (select) { select.innerHTML = ""; const option = document.createElement("option");
          option.textContent = "Library unavailable — reload when saved collections are online"; select.appendChild(option); }
      });
  });
})();
