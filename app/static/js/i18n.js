/* ==========================================================================
   Portal i18n runtime — key-based EN ⇄ HI localization (C-DAC model).

   Resource files: /static/i18n/en.json and /static/i18n/hi.json, keyed
   identically. Nothing is machine-translated at runtime; every user-facing
   string is looked up by key from the active dictionary.

   TWO translation mechanisms, one dictionary:

   1. EXPLICIT keys — markup opts in per node:
        data-i18n="key"              → element textContent
        data-i18n-placeholder="key"  → placeholder attribute
        data-i18n-title="key"        → title attribute
        data-i18n-district="Raipur"  → transliterated place name via
                                       "district.<lowercased value>"
        data-i18n-slot="937 slot"    → only the word "slot" is swapped for
                                       t("value.slotSuffix"); digits stay 0-9

   2. AUTO reverse-index — a map of {english value → key} is built from
      en.json. Every text node and common attribute (placeholder / title /
      aria-label) whose trimmed content EXACTLY matches a dictionary value
      is translated in place; the English original is remembered (WeakMap /
      element expando) so switching back to EN restores it verbatim. This is
      what gives portal-wide coverage — one dictionary entry translates every
      occurrence on every page without per-node markup. Technical codes, IDs,
      usernames and dates never match an entry, so they are never touched.

   A MutationObserver re-runs translation on inserted subtrees, so
   JS-rendered content — SweetAlert2 popups, dropdown panels, dynamic rows —
   is localized too. All writes are guarded (only write when the value
   actually changes), which makes the pipeline idempotent and loop-free.

   Missing keys NEVER blank content: lookup falls back current → en → leave
   the DOM untouched.

   Persistence: localStorage "lang" = "en" | "hi" (default "en"). Switching
   sets <html lang> and fires a "langchange" CustomEvent.
   Public API: window.t(key, params?), window.i18n.{setLang,getLang,apply,district}.
   ========================================================================== */
(function () {
    var STORAGE_KEY = 'lang';
    var LANGS = ['en', 'hi'];
    var DICT_CACHE_PREFIX = 'i18n-dict-';
    var AUTO_ATTRS = ['placeholder', 'title', 'aria-label'];
    var dicts = {};
    var reverse = null;        // trimmed english value -> key (exact)
    var reverseLower = null;   // lowercased english value -> key (fallback)
    var current = 'en';
    var nodeOriginals = (typeof WeakMap === 'function') ? new WeakMap() : null;

    try {
        var saved = localStorage.getItem(STORAGE_KEY);
        if (LANGS.indexOf(saved) !== -1) current = saved;
    } catch (e) { /* private mode */ }

    // <html lang> is set immediately (before first paint) so fonts, screen
    // readers and CSS [lang] hooks are correct from the start.
    document.documentElement.setAttribute('lang', current);

    // Warm start: dictionaries cached from a previous visit apply instantly,
    // so a persisted Hindi choice doesn't flash English while fetching.
    LANGS.forEach(function (l) {
        try {
            var raw = localStorage.getItem(DICT_CACHE_PREFIX + l);
            if (raw) dicts[l] = JSON.parse(raw);
        } catch (e) { /* corrupt cache — refetched below */ }
    });

    function buildReverse() {
        reverse = {};
        reverseLower = {};
        var en = dicts.en || {};
        Object.keys(en).forEach(function (k) {
            // district.* entries participate too: a text node that is exactly
            // a district name transliterates on any page, no markup needed.
            var v = String(en[k]).trim();
            if (!v) return;
            if (!(v in reverse)) reverse[v] = k;
            var lv = v.toLowerCase();
            if (!(lv in reverseLower)) reverseLower[lv] = k;
        });
    }
    if (dicts.en) buildReverse();

    function lookup(key) {
        if (dicts[current] && Object.prototype.hasOwnProperty.call(dicts[current], key)) {
            return dicts[current][key];
        }
        if (dicts.en && Object.prototype.hasOwnProperty.call(dicts.en, key)) {
            return dicts.en[key];
        }
        return null;
    }

    /* t("modal.vAssignAll", {n: 3}) — {placeholders} are substituted after
       lookup so one key serves any dynamic value in either language. */
    function t(key, params) {
        var v = lookup(key);
        if (v === null) return key;
        if (params) {
            Object.keys(params).forEach(function (p) {
                v = v.split('{' + p + '}').join(String(params[p]));
            });
        }
        return v;
    }

    function keyForText(text) {
        if (!reverse) return null;
        if (Object.prototype.hasOwnProperty.call(reverse, text)) return reverse[text];
        var lk = text.toLowerCase();
        if (Object.prototype.hasOwnProperty.call(reverseLower, lk)) return reverseLower[lk];
        return null;
    }

    function districtName(raw) {
        raw = (raw || '').trim();
        if (!raw || current === 'en') return raw;
        var v = lookup('district.' + raw.toLowerCase());
        return v !== null ? v : raw;
    }

    /* ---- auto: text nodes -------------------------------------------------- */
    function translateTextNodes(root) {
        if (!reverse || !nodeOriginals) return;
        var scope = root.nodeType === 3 ? root.parentNode : root;
        if (!scope || scope.nodeType !== 1) return;
        var walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, {
            acceptNode: function (n) {
                var p = n.parentNode;
                if (!p || p.nodeType !== 1) return NodeFilter.FILTER_REJECT;
                var tag = p.nodeName;
                if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEXTAREA') {
                    return NodeFilter.FILTER_REJECT;
                }
                // explicitly keyed nodes are owned by the data-i18n pass
                if (p.hasAttribute && (p.hasAttribute('data-i18n') ||
                    p.hasAttribute('data-i18n-district') || p.hasAttribute('data-i18n-slot'))) {
                    return NodeFilter.FILTER_REJECT;
                }
                return n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
            }
        });
        var n;
        while ((n = walker.nextNode())) {
            var orig = nodeOriginals.get(n);
            var base = orig !== undefined ? orig : n.nodeValue;
            var key = keyForText(base.trim());
            if (!key) continue;
            var v = lookup(key);
            if (v === null) continue;
            if (orig === undefined) nodeOriginals.set(n, n.nodeValue);
            // preserve the node's original leading/trailing whitespace
            var m = base.match(/^(\s*)[\s\S]*?(\s*)$/);
            var next = m[1] + v + m[2];
            if (n.nodeValue !== next) n.nodeValue = next;
        }
    }

    /* ---- auto: attributes --------------------------------------------------- */
    function translateAttrs(root) {
        if (!reverse || root.nodeType !== 1) return;
        AUTO_ATTRS.forEach(function (attr) {
            var sel = '[' + attr.replace(':', '\\:') + ']';
            var els = Array.prototype.slice.call(root.querySelectorAll(sel));
            if (root.hasAttribute && root.hasAttribute(attr)) els.unshift(root);
            els.forEach(function (el) {
                // explicit keys own their attribute
                if (attr === 'placeholder' && el.hasAttribute('data-i18n-placeholder')) return;
                if (attr === 'title' && el.hasAttribute('data-i18n-title')) return;
                var store = el.__i18nAttrs || (el.__i18nAttrs = {});
                var base = store[attr] !== undefined ? store[attr] : el.getAttribute(attr);
                var key = keyForText(String(base).trim());
                if (!key) return;
                var v = lookup(key);
                if (v === null) return;
                if (store[attr] === undefined) store[attr] = base;
                if (el.getAttribute(attr) !== v) el.setAttribute(attr, v);
            });
        });
    }

    /* ---- explicit data-i18n* passes ----------------------------------------- */
    function q(root, sel) {
        var out = Array.prototype.slice.call(root.querySelectorAll(sel));
        if (root.matches && root.matches(sel)) out.unshift(root);
        return out;
    }

    function translateExplicit(root) {
        if (root.nodeType !== 1) return;

        q(root, '[data-i18n]').forEach(function (el) {
            var v = lookup(el.getAttribute('data-i18n'));
            if (v !== null && el.textContent !== v) el.textContent = v;
        });

        q(root, '[data-i18n-placeholder]').forEach(function (el) {
            var v = lookup(el.getAttribute('data-i18n-placeholder'));
            if (v !== null && el.getAttribute('placeholder') !== v) el.setAttribute('placeholder', v);
        });

        q(root, '[data-i18n-title]').forEach(function (el) {
            var v = lookup(el.getAttribute('data-i18n-title'));
            if (v !== null && el.getAttribute('title') !== v) el.setAttribute('title', v);
        });

        // Place names: transliterated, never translated. The attribute holds
        // the original English name so switching back to EN restores it.
        q(root, '[data-i18n-district]').forEach(function (el) {
            var v = districtName(el.getAttribute('data-i18n-district'));
            if (v && el.textContent !== v) el.textContent = v;
        });

        // Slot values like "937 slot": only the unit word is localised;
        // numerals stay Western Arabic per spec.
        q(root, '[data-i18n-slot]').forEach(function (el) {
            var raw = (el.getAttribute('data-i18n-slot') || '').trim();
            if (!raw || !/slot/i.test(raw)) return;
            var v = raw.replace(/slots?/i, t('value.slotSuffix'));
            if (el.textContent !== v) el.textContent = v;
        });
    }

    function apply(root) {
        root = root || document.body || document.documentElement;
        if (!root) return;
        translateTextNodes(root);
        if (root.nodeType === 1) {
            translateAttrs(root);
            translateExplicit(root);
        }
    }

    function announce() {
        document.dispatchEvent(new CustomEvent('langchange', { detail: { lang: current } }));
    }

    function setLang(lang) {
        if (LANGS.indexOf(lang) === -1 || lang === current) return;
        current = lang;
        try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) { /* private mode */ }
        document.documentElement.setAttribute('lang', lang);
        apply();
        announce();
    }

    window.t = t;
    window.i18n = {
        t: t,
        setLang: setLang,
        getLang: function () { return current; },
        apply: apply,
        district: districtName
    };

    /* ---- dynamic content: SweetAlert popups, dropdowns, JS-built rows ------ */
    function observe() {
        if (!('MutationObserver' in window) || !document.body) return;
        var mo = new MutationObserver(function (muts) {
            // Idempotent writes make this safe: re-processing our own
            // mutations converges immediately instead of looping.
            for (var i = 0; i < muts.length; i++) {
                var added = muts[i].addedNodes;
                for (var j = 0; j < added.length; j++) {
                    var n = added[j];
                    if (n.nodeType === 1) apply(n);
                    else if (n.nodeType === 3) translateTextNodes(n);
                }
            }
        });
        mo.observe(document.body, { childList: true, subtree: true });
    }

    /* ---- load dictionaries -------------------------------------------------- */
    Promise.all(LANGS.map(function (l) {
        return fetch('/static/i18n/' + l + '.json')
            .then(function (res) {
                if (!res.ok) throw new Error('i18n: failed to load ' + l);
                return res.json();
            })
            .then(function (dict) {
                dicts[l] = dict;
                try { localStorage.setItem(DICT_CACHE_PREFIX + l, JSON.stringify(dict)); } catch (e) { /* quota */ }
            })
            .catch(function (err) { console.error(err); });
    })).then(function () {
        buildReverse();
        if (document.readyState !== 'loading') { apply(); announce(); }
    });

    document.addEventListener('DOMContentLoaded', function () {
        apply();
        announce();
        observe();
    });
})();
