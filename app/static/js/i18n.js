/* ==========================================================================
   Portal i18n runtime — Key-based & Google Translate Hybrid Model.

   1. Hardcoded dictionary: /static/i18n/en.json and /static/i18n/hi.json.
      - Explicit data-i18n*, data-i18n-placeholder, data-i18n-title,
        data-i18n-district, data-i18n-slot.
      - Auto reverse-index matching exact English strings from en.json.
      - Any element/node translated via dictionary gets marked with `notranslate`
        so Google Translate does not alter official curated Hindi terms.

   2. Google Translate Fallback:
      - Any page content NOT covered by hardcoded dictionary keys is translated
        automatically via Google Translate.
      - Database table cells, status badges, usernames, and technical IDs are
        protected with `notranslate` so raw data is preserved intact.

   Persistence: localStorage "lang" & sessionStorage "portal_lang" = "en" | "hi".
   Cookie: `googtrans=/en/hi` for Hindi; expired/removed for English.
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
        var saved = localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem('portal_lang');
        if (LANGS.indexOf(saved) !== -1) current = saved;
    } catch (e) { /* private mode */ }

    // <html lang> is set immediately (before first paint)
    document.documentElement.setAttribute('lang', current);

    // Warm start: dictionaries cached from a previous visit apply instantly
    LANGS.forEach(function (l) {
        try {
            var raw = localStorage.getItem(DICT_CACHE_PREFIX + l);
            if (raw) dicts[l] = JSON.parse(raw);
        } catch (e) { /* corrupt cache */ }
    });

    function setGoogTransCookie(lang) {
        var domain = window.location.hostname;
        if (lang === 'hi') {
            document.cookie = "googtrans=/en/hi; path=/;";
            document.cookie = "googtrans=/en/hi; path=/; domain=." + domain;
        } else {
            document.cookie = "googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            document.cookie = "googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=." + domain;
        }
    }

    function buildReverse() {
        reverse = {};
        reverseLower = {};
        var en = dicts.en || {};
        Object.keys(en).forEach(function (k) {
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

    /* ---- Protect raw database table cells & status badges ---- */
    function excludeDatabaseTables(root) {
        root = root || document.body || document.documentElement;
        if (!root || current !== 'hi') return;
        var tds = root.querySelectorAll ? root.querySelectorAll('td') : [];
        for (var k = 0; k < tds.length; k++) {
            var el = tds[k];
            var isActionButton = el.querySelector('button, a.btn, input[type="button"], input[type="submit"]');
            var isStatusBadge = el.querySelector('[class*="badge"], [class*="status"]');

            if (isStatusBadge || (!isActionButton)) {
                el.classList.add('notranslate');
                el.setAttribute('translate', 'no');
                var children = el.querySelectorAll('*');
                for (var i = 0; i < children.length; i++) {
                    children[i].classList.add('notranslate');
                    children[i].setAttribute('translate', 'no');
                }
            }
        }
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
            var m = base.match(/^(\s*)[\s\S]*?(\s*)$/);
            var next = current === 'hi' ? (m[1] + v + m[2]) : (m[1] + base.trim() + m[2]);
            if (n.nodeValue !== next) n.nodeValue = next;

            var p = n.parentNode;
            if (p && p.nodeType === 1) {
                if (current === 'hi') {
                    p.classList.add('notranslate');
                    p.setAttribute('translate', 'no');
                } else {
                    p.classList.remove('notranslate');
                    p.removeAttribute('translate');
                }
            }
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
                if (attr === 'placeholder' && el.hasAttribute('data-i18n-placeholder')) return;
                if (attr === 'title' && el.hasAttribute('data-i18n-title')) return;
                var store = el.__i18nAttrs || (el.__i18nAttrs = {});
                var base = store[attr] !== undefined ? store[attr] : el.getAttribute(attr);
                var key = keyForText(String(base).trim());
                if (!key) return;
                var v = lookup(key);
                if (v === null) return;
                if (store[attr] === undefined) store[attr] = base;
                var targetVal = current === 'hi' ? v : base;
                if (el.getAttribute(attr) !== targetVal) el.setAttribute(attr, targetVal);
                if (current === 'hi') {
                    el.classList.add('notranslate');
                    el.setAttribute('translate', 'no');
                } else {
                    el.classList.remove('notranslate');
                    el.removeAttribute('translate');
                }
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
            if (v !== null) {
                if (el.textContent !== v) el.textContent = v;
                if (current === 'hi') {
                    el.classList.add('notranslate');
                    el.setAttribute('translate', 'no');
                } else {
                    el.classList.remove('notranslate');
                    el.removeAttribute('translate');
                }
            }
        });

        q(root, '[data-i18n-placeholder]').forEach(function (el) {
            var v = lookup(el.getAttribute('data-i18n-placeholder'));
            if (v !== null) {
                if (el.getAttribute('placeholder') !== v) el.setAttribute('placeholder', v);
                if (current === 'hi') {
                    el.classList.add('notranslate');
                    el.setAttribute('translate', 'no');
                } else {
                    el.classList.remove('notranslate');
                    el.removeAttribute('translate');
                }
            }
        });

        q(root, '[data-i18n-title]').forEach(function (el) {
            var v = lookup(el.getAttribute('data-i18n-title'));
            if (v !== null) {
                if (el.getAttribute('title') !== v) el.setAttribute('title', v);
                if (current === 'hi') {
                    el.classList.add('notranslate');
                    el.setAttribute('translate', 'no');
                } else {
                    el.classList.remove('notranslate');
                    el.removeAttribute('translate');
                }
            }
        });

        q(root, '[data-i18n-district]').forEach(function (el) {
            var v = districtName(el.getAttribute('data-i18n-district'));
            if (v) {
                if (el.textContent !== v) el.textContent = v;
                if (current === 'hi') {
                    el.classList.add('notranslate');
                    el.setAttribute('translate', 'no');
                } else {
                    el.classList.remove('notranslate');
                    el.removeAttribute('translate');
                }
            }
        });

        q(root, '[data-i18n-slot]').forEach(function (el) {
            var raw = (el.getAttribute('data-i18n-slot') || '').trim();
            if (!raw || !/slot/i.test(raw)) return;
            var v = current === 'hi' ? raw.replace(/slots?/i, t('value.slotSuffix')) : raw;
            if (el.textContent !== v) el.textContent = v;
            if (current === 'hi') {
                el.classList.add('notranslate');
                el.setAttribute('translate', 'no');
            } else {
                el.classList.remove('notranslate');
                el.removeAttribute('translate');
            }
        });
    }

    function apply(root) {
        root = root || document.body || document.documentElement;
        if (!root) return;
        excludeDatabaseTables(root);
        translateTextNodes(root);
        if (root.nodeType === 1) {
            translateAttrs(root);
            translateExplicit(root);
        }
    }

    function announce() {
        document.dispatchEvent(new CustomEvent('langchange', { detail: { lang: current } }));
    }

    function setLang(lang, shouldReload) {
        if (LANGS.indexOf(lang) === -1) return;
        var changed = (lang !== current);
        current = lang;
        try {
            localStorage.setItem(STORAGE_KEY, lang);
            sessionStorage.setItem('portal_lang', lang);
        } catch (e) { /* private mode */ }
        document.documentElement.setAttribute('lang', lang);
        setGoogTransCookie(lang);

        if (shouldReload !== false) {
            window.location.reload();
            return;
        }

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
    window.togglePortalLanguage = function () {
        setLang(current === 'en' ? 'hi' : 'en', true);
    };

    /* ---- dynamic content: SweetAlert popups, dropdowns, JS-built rows ------ */
    function observe() {
        if (!('MutationObserver' in window) || !document.body) return;
        var mo = new MutationObserver(function (muts) {
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
