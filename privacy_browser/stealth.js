// Disuntikkan ke setiap frame sebelum script halaman berjalan.
// Memalsukan fingerprint secara konsisten (seed per profil) dan menyamarkan patch sebagai fungsi native.
(() => {
  'use strict';
  const FP = /*__FP__*/null;
  if (!FP) return;

  const hash32 = (x) => {
    x = Math.imul(x ^ (x >>> 16), 0x45d9f3b);
    x = Math.imul(x ^ (x >>> 16), 0x45d9f3b);
    return (x ^ (x >>> 16)) >>> 0;
  };
  const strHash = (s) => {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) | 0;
    return h >>> 0;
  };

  // ---------- Samarkan patch: fn.toString() mengembalikan "[native code]" ----------
  const nativeFnToString = Function.prototype.toString;
  const nativeStrings = new WeakMap();
  const fakeToString = {
    toString() {
      if (nativeStrings.has(this)) return nativeStrings.get(this);
      return nativeFnToString.call(this);
    },
  }.toString;
  nativeStrings.set(fakeToString, nativeFnToString.call(nativeFnToString));
  Object.defineProperty(Function.prototype, 'toString', {
    value: fakeToString, writable: true, configurable: true, enumerable: false,
  });
  const asNative = (fn, name) => {
    nativeStrings.set(fn, `function ${name}() { [native code] }`);
    return fn;
  };

  const defineGetter = (proto, prop, getValue) => {
    const desc = Object.getOwnPropertyDescriptor(proto, prop);
    if (!desc || !desc.get) return;
    const getter = Object.getOwnPropertyDescriptor(
      { get [prop]() { return getValue.call(this, desc.get); } }, prop).get;
    asNative(getter, 'get ' + prop);
    Object.defineProperty(proto, prop, { ...desc, get: getter });
  };

  const replaceMethod = (proto, name, factory) => {
    if (!proto) return;
    const desc = Object.getOwnPropertyDescriptor(proto, name);
    if (!desc || typeof desc.value !== 'function') return;
    const impl = factory(desc.value);
    const wrapped = { [name](...args) { return impl.apply(this, args); } }[name];
    Object.defineProperty(wrapped, 'length', { value: desc.value.length });
    asNative(wrapped, name);
    Object.defineProperty(proto, name, { ...desc, value: wrapped });
  };

  // ---------- Navigator ----------
  const N = Navigator.prototype;
  if (FP.hardwareConcurrency) defineGetter(N, 'hardwareConcurrency', () => FP.hardwareConcurrency);
  if (FP.deviceMemory) defineGetter(N, 'deviceMemory', () => FP.deviceMemory);
  if (FP.platform) defineGetter(N, 'platform', () => FP.platform);
  if (FP.languages && FP.languages.length) {
    const langs = Object.freeze([...FP.languages]);
    defineGetter(N, 'languages', () => langs);
    defineGetter(N, 'language', () => langs[0]);
  }

  // ---------- Screen ----------
  if (FP.screen && window.Screen) {
    const S = Screen.prototype;
    const s = FP.screen;
    defineGetter(S, 'width', () => s.width);
    defineGetter(S, 'height', () => s.height);
    defineGetter(S, 'availWidth', () => s.availWidth);
    defineGetter(S, 'availHeight', () => s.availHeight);
    defineGetter(S, 'availLeft', () => 0);
    defineGetter(S, 'availTop', () => 0);
    defineGetter(S, 'colorDepth', () => 24);
    defineGetter(S, 'pixelDepth', () => 24);

    // Jendela tidak boleh terlihat lebih besar dari layar palsu
    // (mis. saat user memaksimalkan jendela di monitor yang lebih besar).
    defineGetter(window, 'innerWidth', (origGet) => Math.min(origGet.call(window), s.width));
    defineGetter(window, 'outerWidth', (origGet) => Math.min(origGet.call(window), s.width));
    defineGetter(window, 'innerHeight', (origGet) => Math.min(origGet.call(window), s.availHeight));
    defineGetter(window, 'outerHeight', (origGet) => Math.min(origGet.call(window), s.height));

    // matchMedia: device-width/device-height harus cocok dengan screen palsu
    const deviceRe = /^\s*(?:only\s+screen\s+and\s+)?\(\s*(min-|max-)?device-(width|height)\s*:\s*([\d.]+)px\s*\)\s*$/;
    const matchMediaWrapped = {
      matchMedia(query) {
        const m = typeof query === 'string' ? query.match(deviceRe) : null;
        if (m) {
          const target = m[2] === 'width' ? s.width : s.height;
          const n = parseFloat(m[3]);
          const matches = m[1] === 'min-' ? target >= n : m[1] === 'max-' ? target <= n : target === n;
          return {
            matches, media: query, onchange: null,
            addEventListener() {}, removeEventListener() {},
            addListener() {}, removeListener() {},
            dispatchEvent() { return false; },
          };
        }
        return matchMediaWrapped.__orig.call(this, query);
      },
    }.matchMedia;
    const mmDesc = Object.getOwnPropertyDescriptor(window, 'matchMedia');
    if (mmDesc && typeof mmDesc.value === 'function') {
      matchMediaWrapped.__orig = mmDesc.value;
      Object.defineProperty(matchMediaWrapped, 'length', { value: mmDesc.value.length });
      asNative(matchMediaWrapped, 'matchMedia');
      Object.defineProperty(window, 'matchMedia', { ...mmDesc, value: matchMediaWrapped });
    }
  }

  // ---------- Worker: init script tidak jalan di dalam Worker/SharedWorker, ----------
  // jadi bungkus konstruktornya dan suntikkan spoof ke script worker-nya.
  // Fungsi ini diserialisasi ke dalam worker (harus mandiri). Dengan opts.main ia
  // hanya mengembalikan pembungkus konstruktor untuk dipakai di halaman.
  const workerStealth = (cfg, selfSrc, opts) => {
    const main = !!(opts && opts.main);
    let markNative = main ? opts.markNative : null;
    const makeWrapper = (NativeCtor, ctorName, prelude) => {
      const cache = new Map();
      const build = (url, isModule) => {
        const abs = new URL(url, main ? document.baseURI : self.location.href).href;
        const key = (isModule ? 'm:' : 'c:') + abs;
        if (cache.has(key)) return cache.get(key);
        let blobUrl = null;
        try {
          if (isModule) {
            // prelude dulu, lalu impor modul asli (impor relatif tetap benar karena
            // modul di-resolve terhadap URL aslinya)
            if (new URL(abs).origin === self.location.origin) {
              blobUrl = URL.createObjectURL(new Blob(
                [prelude, `\nawait import(${JSON.stringify(abs)});\n`], { type: 'text/javascript' }));
            }
          } else {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', abs, false); // sync XHR: konstruktor harus sinkron
            xhr.send();
            if (xhr.status < 400 && xhr.responseText) {
              // importScripts() dengan URL relatif di-resolve ke script asal, bukan blob:
              const fix =
                `\n;self.importScripts=((f)=>(...u)=>f(...u.map((x)=>new URL(x,${JSON.stringify(abs)}).href)))(self.importScripts);\n`;
              blobUrl = URL.createObjectURL(
                new Blob([prelude, fix, xhr.responseText], { type: 'text/javascript' }));
            }
          }
        } catch (e) {
          blobUrl = null; // gagal: pakai worker asli
        }
        cache.set(key, blobUrl);
        return blobUrl;
      };
      const Wrapped = function (url, o) {
        if (!new.target) return NativeCtor(url, o); // lempar TypeError seperti aslinya
        const isModule = !!(o && typeof o === 'object' && o.type === 'module');
        let blobUrl = null;
        try { blobUrl = build(url, isModule); } catch (e) { /* abaikan */ }
        return new NativeCtor(blobUrl || url, o);
      };
      Wrapped.prototype = NativeCtor.prototype;
      try {
        Object.defineProperty(Wrapped, 'length', { value: NativeCtor.length });
        Object.defineProperty(Wrapped, 'name', { value: ctorName });
      } catch (e) { /* abaikan */ }
      markNative(Wrapped, `function ${ctorName}() { [native code] }`);
      return Wrapped;
    };
    if (main) return makeWrapper;

    try {
      const pToString = Function.prototype.toString;
      const map = new WeakMap();
      const fake = {
        toString() { return map.has(this) ? map.get(this) : pToString.call(this); },
      }.toString;
      map.set(fake, pToString.call(pToString));
      Object.defineProperty(Function.prototype, 'toString', {
        value: fake, writable: true, configurable: true, enumerable: false,
      });
      markNative = (fn, str) => map.set(fn, str);
      const hash32 = (x) => {
        x = Math.imul(x ^ (x >>> 16), 0x45d9f3b);
        x = Math.imul(x ^ (x >>> 16), 0x45d9f3b);
        return (x ^ (x >>> 16)) >>> 0;
      };
      const def = (obj, prop, value) => {
        try {
          const g = Object.getOwnPropertyDescriptor({ get [prop]() { return value; } }, prop).get;
          map.set(g, `function get ${prop}() { [native code] }`);
          Object.defineProperty(obj, prop, { get: g, configurable: true, enumerable: true });
        } catch (e) { /* abaikan */ }
      };
      const replace = (proto, name, factory) => {
        if (!proto) return;
        const d = Object.getOwnPropertyDescriptor(proto, name);
        if (!d || typeof d.value !== 'function') return;
        const impl = factory(d.value);
        const w = { [name](...a) { return impl.apply(this, a); } }[name];
        Object.defineProperty(w, 'length', { value: d.value.length });
        map.set(w, `function ${name}() { [native code] }`);
        Object.defineProperty(proto, name, { ...d, value: w });
      };

      // Navigator
      const NP = (typeof WorkerNavigator !== 'undefined' && WorkerNavigator.prototype)
        || (typeof navigator !== 'undefined' && Object.getPrototypeOf(navigator));
      if (NP) {
        if (cfg.hardwareConcurrency) def(NP, 'hardwareConcurrency', cfg.hardwareConcurrency);
        if (cfg.deviceMemory) def(NP, 'deviceMemory', cfg.deviceMemory);
        if (cfg.platform) def(NP, 'platform', cfg.platform);
        if (cfg.languages && cfg.languages.length) {
          def(NP, 'languages', Object.freeze(cfg.languages.slice()));
          def(NP, 'language', cfg.languages[0]);
        }
      }

      // WebGL di OffscreenCanvas: GPU asli sama di semua profil -> harus dipalsukan juga
      const glp = cfg.webglParams || {};
      const patchGL = (proto) => {
        replace(proto, 'getParameter', (orig) => function (p) {
          if (p === 37445 && cfg.webglVendor) return cfg.webglVendor;
          if (p === 37446 && cfg.webglRenderer) return cfg.webglRenderer;
          const k = String(p);
          if (k in glp && !(p === 34047 && !this.getExtension('EXT_texture_filter_anisotropic'))) {
            const v = glp[k];
            if (Array.isArray(v)) return (p === 33901 || p === 33902) ? new Float32Array(v) : new Int32Array(v);
            return v;
          }
          return orig.call(this, p);
        });
        if (cfg.webglSeed) {
          replace(proto, 'readPixels', (orig) => function (...a) {
            const r = orig.apply(this, a);
            const px = a[6];
            if (px && px.length) {
              for (let i = 0; i < px.length; i += 4) {
                if ((hash32(cfg.webglSeed ^ i) & 31) === 0) px[i] ^= 1;
              }
            }
            return r;
          });
        }
      };
      if (typeof WebGLRenderingContext !== 'undefined') patchGL(WebGLRenderingContext.prototype);
      if (typeof WebGL2RenderingContext !== 'undefined') patchGL(WebGL2RenderingContext.prototype);

      // Canvas noise di OffscreenCanvas (sama dengan noise di halaman)
      if (cfg.canvasSeed && typeof OffscreenCanvasRenderingContext2D !== 'undefined') {
        const seed = cfg.canvasSeed | 0;
        const C2D = OffscreenCanvasRenderingContext2D.prototype;
        const origGet = C2D.getImageData;
        const origPut = C2D.putImageData;
        const noise = (d) => {
          for (let i = 0; i < d.length; i += 4) {
            if (d[i + 3] === 0) continue;
            const h = hash32(seed ^ i);
            if ((h & 15) === 0) d[i + ((h >>> 4) % 3)] ^= 1;
          }
        };
        replace(C2D, 'getImageData', (orig) => function (...a) {
          const img = orig.apply(this, a);
          noise(img.data);
          return img;
        });
        if (typeof OffscreenCanvas !== 'undefined') {
          replace(OffscreenCanvas.prototype, 'convertToBlob', (orig) => function (...a) {
            const w = this.width, h = this.height;
            if (w && h && w * h <= 16e6) {
              try {
                const c = new OffscreenCanvas(w, h);
                const ctx = c.getContext('2d');
                ctx.drawImage(this, 0, 0);
                const img = origGet.call(ctx, 0, 0, w, h);
                noise(img.data);
                origPut.call(ctx, img, 0, 0);
                return orig.apply(c, a);
              } catch (e) { /* pakai kanvas asli */ }
            }
            return orig.apply(this, a);
          });
        }
      }

      // Worker di dalam Worker
      if (typeof self.Worker === 'function' && selfSrc) {
        const pre = `;(${selfSrc})(${JSON.stringify(cfg)}, ${JSON.stringify(selfSrc)});`;
        self.Worker = makeWrapper(self.Worker, 'Worker', pre);
      }
    } catch (e) { /* abaikan */ }
  };
  const workerStealthSrc = workerStealth.toString();
  const WORKER_CFG = {
    hardwareConcurrency: FP.hardwareConcurrency,
    deviceMemory: FP.deviceMemory,
    platform: FP.platform,
    languages: FP.languages,
    webglVendor: FP.webglVendor,
    webglRenderer: FP.webglRenderer,
    webglParams: FP.webglParams,
    webglSeed: FP.webglSeed,
    canvasSeed: FP.canvasSeed,
  };
  const WORKER_PRELUDE =
    `;(${workerStealthSrc})(${JSON.stringify(WORKER_CFG)}, ${JSON.stringify(workerStealthSrc)});`;
  const makeWorkerWrapper = workerStealth(WORKER_CFG, null, {
    main: true, markNative: (fn, str) => nativeStrings.set(fn, str),
  });
  // Catatan: SharedWorker yang dibungkus jadi per-tab (URL blob berbeda tiap halaman),
  // tapi tetap berfungsi normal di dalam satu tab.
  for (const name of ['Worker', 'SharedWorker']) {
    if (typeof window[name] !== 'function') continue;
    Object.defineProperty(window, name, {
      value: makeWorkerWrapper(window[name], name, WORKER_PRELUDE),
      writable: true, configurable: true, enumerable: false,
    });
  }

  // ---------- Service Worker: tidak bisa disuntik spoof, jadi pendaftarannya ----------
  // ditolak seperti saat Chrome memblokir penyimpanan situs.
  if (FP.blockServiceWorker && window.ServiceWorkerContainer) {
    replaceMethod(ServiceWorkerContainer.prototype, 'register', () => function (url, o) {
      let script = String(url), scope = '';
      try {
        script = new URL(url, document.baseURI).href;
        scope = new URL((o && o.scope) || './', script).href;
      } catch (e) { /* abaikan */ }
      return Promise.reject(new DOMException(
        `Failed to register a ServiceWorker for scope ('${scope}') with script ('${script}'): ` +
        'The user denied permission to use Service Worker.', 'SecurityError'));
    });
  }

  // ---------- Canvas noise (deterministik per profil) ----------
  if (FP.canvasSeed && window.CanvasRenderingContext2D) {
    const seed = FP.canvasSeed | 0;
    const C2D = CanvasRenderingContext2D.prototype;
    const origGetImageData = C2D.getImageData;
    const origPutImageData = C2D.putImageData;
    const noise = (d) => {
      for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] === 0) continue;
        const h = hash32(seed ^ i);
        if ((h & 15) === 0) d[i + ((h >>> 4) % 3)] ^= 1;
      }
    };
    replaceMethod(C2D, 'getImageData', (orig) => function (...a) {
      const img = orig.apply(this, a);
      noise(img.data);
      return img;
    });
    const noisyCopy = (canvas) => {
      const w = canvas.width, h = canvas.height;
      if (!w || !h || w * h > 16e6) return canvas;
      try {
        const c = document.createElement('canvas');
        c.width = w; c.height = h;
        const ctx = c.getContext('2d');
        ctx.drawImage(canvas, 0, 0);
        const img = origGetImageData.call(ctx, 0, 0, w, h);
        noise(img.data);
        origPutImageData.call(ctx, img, 0, 0);
        return c;
      } catch (e) {
        return canvas;
      }
    };
    const HC = HTMLCanvasElement.prototype;
    replaceMethod(HC, 'toDataURL', (orig) => function (...a) { return orig.apply(noisyCopy(this), a); });
    replaceMethod(HC, 'toBlob', (orig) => function (...a) { return orig.apply(noisyCopy(this), a); });
  }

  // ---------- Font noise: lebar teks digeser sedikit per profil supaya ----------
  // enumerasi font (via measureText) tidak sama di semua profil.
  if (FP.fontSeed && window.CanvasRenderingContext2D) {
    const fseed = FP.fontSeed | 0;
    const metricRe = /^(width|actualBoundingBox|fontBoundingBox|emHeight|alphabeticBaseline|hangingBaseline)/;
    replaceMethod(CanvasRenderingContext2D.prototype, 'measureText', (orig) => function (text) {
      const m = orig.call(this, text);
      const h = hash32(fseed ^ strHash(String(this.font) + '|' + String(text)));
      const scale = 1 + ((h % 2000) - 1000) / 2e6; // ±0.05%, deterministik per (profil, font, teks)
      if (scale === 1) return m;
      return new Proxy(m, {
        get(t, p) {
          const v = Reflect.get(t, p);
          if (typeof v === 'number' && typeof p === 'string' && metricRe.test(p)) return v * scale;
          return v;
        },
      });
    });
  }

  // ---------- WebGL vendor/renderer + parameter konsisten per GPU + noise ----------
  const glParamOverride = (ctx, p) => {
    const params = FP.webglParams;
    if (!params) return undefined;
    const key = String(p);
    if (!(key in params)) return undefined;
    // anisotropy hanya valid kalau ekstensinya diaktifkan
    if (p === 34047 && !ctx.getExtension('EXT_texture_filter_anisotropic')) return undefined;
    const v = params[key];
    if (Array.isArray(v)) {
      return (p === 33901 || p === 33902) ? new Float32Array(v) : new Int32Array(v);
    }
    return v;
  };
  const patchGL = (proto) => {
    if (!proto) return;
    replaceMethod(proto, 'getParameter', (orig) => function (p) {
      if (p === 37445 && FP.webglVendor) return FP.webglVendor;     // UNMASKED_VENDOR_WEBGL
      if (p === 37446 && FP.webglRenderer) return FP.webglRenderer; // UNMASKED_RENDERER_WEBGL
      const o = glParamOverride(this, p);
      if (o !== undefined) return o;
      return orig.call(this, p);
    });
    if (FP.webglSeed) {
      replaceMethod(proto, 'readPixels', (orig) => function (...a) {
        const r = orig.apply(this, a);
        const px = a[6];
        if (px && px.length) {
          for (let i = 0; i < px.length; i += 4) {
            if ((hash32(FP.webglSeed ^ i) & 31) === 0) px[i] ^= 1;
          }
        }
        return r;
      });
    }
  };
  patchGL(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
  patchGL(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);

  // ---------- Audio noise ----------
  if (FP.audioSeed && window.AudioBuffer) {
    const seed = FP.audioSeed | 0;
    const done = new WeakMap();
    replaceMethod(AudioBuffer.prototype, 'getChannelData', (orig) => function (ch) {
      const data = orig.call(this, ch);
      let set = done.get(this);
      if (!set) { set = new Set(); done.set(this, set); }
      if (!set.has(ch)) {
        set.add(ch);
        for (let i = 0; i < data.length; i += 97) {
          data[i] += ((hash32(seed ^ i) / 4294967296) - 0.5) * 2e-7;
        }
      }
      return data;
    });
    if (window.AnalyserNode) {
      replaceMethod(AnalyserNode.prototype, 'getFloatFrequencyData', (orig) => function (arr) {
        const r = orig.call(this, arr);
        for (let i = 0; i < arr.length; i += 13) {
          arr[i] += ((hash32(seed ^ i) / 4294967296) - 0.5) * 1e-4;
        }
        return r;
      });
    }
  }

  // ---------- Daftar suara: pakai set bawaan Windows + Chrome yang umum ----------
  if (window.SpeechSynthesis) {
    const mkVoice = (name, lang, def) => ({
      name, lang, voiceURI: name, default: def, localService: true,
    });
    const VOICES = [
      mkVoice('Microsoft David - English (United States)', 'en-US', true),
      mkVoice('Microsoft Zira - English (United States)', 'en-US', false),
      mkVoice('Microsoft Mark - English (United States)', 'en-US', false),
      mkVoice('Google US English', 'en-US', false),
    ];
    replaceMethod(SpeechSynthesis.prototype, 'getVoices', () => function () { return VOICES.slice(); });
  }

  // ---------- Perangkat media: set standar (mic + kamera + speaker) ----------
  if (window.MediaDevices && navigator.mediaDevices) {
    const mkDevice = (deviceId, kind) => ({
      deviceId, kind, label: '', groupId: '',
      toJSON() { return { deviceId: this.deviceId, groupId: this.groupId, kind: this.kind, label: this.label }; },
    });
    const DEVICES = [
      mkDevice('default', 'audioinput'),
      mkDevice('', 'videoinput'),
      mkDevice('default', 'audiooutput'),
      mkDevice('communications', 'audiooutput'),
    ];
    replaceMethod(MediaDevices.prototype, 'enumerateDevices', () => function () {
      return Promise.resolve(DEVICES.map((d) => ({ ...d })));
    });
  }

  // ---------- WebRTC ----------
  if (FP.webrtc === 'disable') {
    for (const k of ['RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', 'RTCSessionDescription', 'RTCIceCandidate']) {
      try { delete window[k]; } catch (e) { /* abaikan */ }
    }
  }
})();
