/**
 * Universal Searchable Combobox Component
 * Hybrid: Real-time Live Suggestion Search (YouTube/Google style) + Full Dropdown Browse
 */
(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.SearchableCombobox = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function highlightMatch(text, query) {
        if (!text) return '';
        if (!query) return escapeHtml(text);
        const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
        return escapeHtml(text).replace(regex, '<mark class="sc-highlight">$1</mark>');
    }

    class SearchableCombobox {
        constructor(options) {
            this.options = Object.assign({
                container: null,
                placeholder: 'Search operator by name, ID, mobile, email...',
                endpoint: null,
                items: [],
                onSelect: null,
                onClear: null,
                renderItem: null,
                debounceMs: 150,
                autoFocus: false,
                initialValue: '',
                inputName: 'operator_search'
            }, options);

            this.items = Array.isArray(this.options.items) ? [...this.options.items] : [];
            this.filteredItems = [];
            this.selectedItem = null;
            this.selectedIndex = -1;
            this.isOpen = false;
            this.isLoading = false;
            this.debounceTimer = null;

            this.container = typeof this.options.container === 'string'
                ? document.querySelector(this.options.container)
                : this.options.container;

            if (!this.container) {
                console.error('[SearchableCombobox] Container element not found.');
                return;
            }

            this._init();
        }

        _init() {
            this.container.innerHTML = '';
            
            this.wrapper = document.createElement('div');
            this.wrapper.className = 'sc-combobox-wrapper';

            this.inputContainer = document.createElement('div');
            this.inputContainer.className = 'sc-input-container';

            // Search Icon
            this.searchIcon = document.createElement('span');
            this.searchIcon.className = 'sc-search-icon';
            this.searchIcon.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`;

            // Input element
            this.input = document.createElement('input');
            this.input.type = 'text';
            this.input.className = 'sc-input notranslate';
            this.input.setAttribute('translate', 'no');
            this.input.dataset.transliterationSetup = 'ignore';
            this.input.placeholder = this.options.placeholder;
            this.input.name = this.options.inputName;
            this.input.autocomplete = 'off';
            this.input.spellcheck = false;
            if (this.options.initialValue) {
                this.input.value = this.options.initialValue;
            }

            // Actions group (Clear + Spinner + Chevron Toggle)
            this.actionsGroup = document.createElement('div');
            this.actionsGroup.className = 'sc-actions-group';

            this.spinner = document.createElement('span');
            this.spinner.className = 'sc-spinner';
            this.spinner.style.display = 'none';

            this.clearBtn = document.createElement('button');
            this.clearBtn.type = 'button';
            this.clearBtn.className = 'sc-clear-btn';
            this.clearBtn.title = 'Clear search';
            this.clearBtn.style.display = this.input.value ? 'flex' : 'none';
            this.clearBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;

            this.toggleBtn = document.createElement('button');
            this.toggleBtn.type = 'button';
            this.toggleBtn.className = 'sc-toggle-btn';
            this.toggleBtn.title = 'Browse all options';
            this.toggleBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>`;

            this.actionsGroup.appendChild(this.spinner);
            this.actionsGroup.appendChild(this.clearBtn);
            this.actionsGroup.appendChild(this.toggleBtn);

            this.inputContainer.appendChild(this.searchIcon);
            this.inputContainer.appendChild(this.input);
            this.inputContainer.appendChild(this.actionsGroup);

            // Dropdown Menu
            this.dropdownMenu = document.createElement('ul');
            this.dropdownMenu.className = 'sc-dropdown-menu';
            this.dropdownMenu.setAttribute('role', 'listbox');

            this.wrapper.appendChild(this.inputContainer);
            this.wrapper.appendChild(this.dropdownMenu);
            this.container.appendChild(this.wrapper);

            this._bindEvents();

            if (this.options.autoFocus) {
                setTimeout(() => this.input.focus(), 100);
            }
        }

        _bindEvents() {
            // Typing / Input Event
            this.input.addEventListener('input', (e) => {
                const query = e.target.value;
                this.clearBtn.style.display = query ? 'flex' : 'none';
                this.selectedItem = null;

                clearTimeout(this.debounceTimer);
                this.debounceTimer = setTimeout(() => {
                    this._handleSearch(query);
                }, this.options.debounceMs);
            });

            // Focus Event: Show suggestions or full list
            this.input.addEventListener('focus', () => {
                this._handleSearch(this.input.value);
            });

            // Toggle Dropdown Button
            this.toggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (this.isOpen) {
                    this.close();
                } else {
                    this.input.focus();
                    this._handleSearch('');
                }
            });

            // Clear Button
            this.clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.clear();
                this.input.focus();
                this._handleSearch('');
            });

            // Keyboard Navigation
            this.input.addEventListener('keydown', (e) => {
                if (!this.isOpen) {
                    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                        e.preventDefault();
                        this._handleSearch(this.input.value);
                        return;
                    }
                }

                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    this._moveSelection(1);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    this._moveSelection(-1);
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    if (this.selectedIndex >= 0 && this.filteredItems[this.selectedIndex]) {
                        this.selectItem(this.filteredItems[this.selectedIndex]);
                    }
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    this.close();
                }
            });

            // Click outside to close
            this._outsideClickListener = (e) => {
                if (!this.wrapper.contains(e.target)) {
                    this.close();
                }
            };
            document.addEventListener('click', this._outsideClickListener);
        }

        async _handleSearch(query) {
            query = (query || '').trim();

            if (this.options.endpoint) {
                // Fetch from remote backend endpoint
                this._setLoading(true);
                try {
                    const sep = this.options.endpoint.includes('?') ? '&' : '?';
                    const url = `${this.options.endpoint}${sep}q=${encodeURIComponent(query)}`;
                    const res = await fetch(url);
                    if (res.ok) {
                        const data = await res.json();
                        let results = Array.isArray(data) ? data : (data.items || data.results || data.operators || data.candidates || []);
                        this.filteredItems = results;
                        this._renderDropdown(query);
                    }
                } catch (err) {
                    console.error('[SearchableCombobox] Search fetch error:', err);
                } finally {
                    this._setLoading(false);
                }
            } else {
                // Filter local items array
                if (!query) {
                    this.filteredItems = [...this.items];
                } else {
                    const qLower = query.toLowerCase();
                    this.filteredItems = this.items.filter(item => {
                        const str = this._getItemSearchString(item).toLowerCase();
                        return str.includes(qLower);
                    });
                }
                this._renderDropdown(query);
            }
        }

        _getItemSearchString(item) {
            if (typeof item === 'string') return item;
            return [
                item.name,
                item.operator_name,
                item.operator_id,
                item.user_code,
                item.id,
                item.mobile,
                item.operator_mobile,
                item.email,
                item.primary_email,
                item.email_id,
                item.aadhaar,
                item.operator_aadhaar,
                item.station_id,
                item.new_station_id,
                item.model,
                item.model_type,
                item.machine_id,
                item.district_name,
                item.district,
                item.nseit_id,
                item.reason,
                item.inactive_reason,
                item.deactivation_reason
            ].filter(Boolean).join(' ');
        }

        _renderDropdown(query) {
            this.dropdownMenu.innerHTML = '';
            this.selectedIndex = -1;

            if (this.filteredItems.length === 0) {
                const empty = document.createElement('li');
                empty.className = 'sc-empty-state';
                empty.textContent = query ? `No matching options for "${query}"` : 'No available options found';
                this.dropdownMenu.appendChild(empty);
            } else {
                this.filteredItems.forEach((item, index) => {
                    const li = document.createElement('li');
                    li.className = 'sc-dropdown-item';
                    li.setAttribute('role', 'option');
                    li.setAttribute('data-index', index);

                    if (this.options.renderItem) {
                        li.innerHTML = this.options.renderItem(item, query, highlightMatch);
                    } else {
                        li.innerHTML = this._defaultRenderItem(item, query);
                    }

                    li.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.selectItem(item);
                    });

                    this.dropdownMenu.appendChild(li);
                });
            }

            this.open();
        }

        _defaultRenderItem(item, query) {
            // Station ID item support
            if (item.station_id || item.new_station_id) {
                const sid = String(item.station_id || item.new_station_id);
                const model = item.model || item.model_type || 'ECMP';
                const district = item.district_name || item.district || '';
                const machine = item.machine_id ? `Machine: ${item.machine_id}` : '';
                const highlightedSid = highlightMatch(sid, query);
                const highlightedModel = highlightMatch(model, query);

                return `
                    <div class="sc-item-header">
                        <span class="sc-item-title" style="font-family: monospace; font-size: 14px; font-weight: 700;">${highlightedSid}</span>
                        <span class="sc-item-badge" style="background: #e0e7ff; color: #3730a3; font-weight: 700;">${highlightedModel}</span>
                    </div>
                    ${(district || machine) ? `<div class="sc-item-subtext">${[district, machine].filter(Boolean).join(' · ')}</div>` : ''}
                `;
            }

            const name = item.name || item.operator_name || 'Unnamed Operator';
            const opId = item.request_code || item.operator_id || item.user_code || '';
            const mobile = item.mobile || item.operator_mobile || '';
            const email = item.email || item.primary_email || item.email_id || '';
            const nseit = item.nseit_id || '';
            const status = item.status || item.inactive_reason || item.deactivation_reason || '';

            const highlightedName = highlightMatch(name, query);
            const highlightedOpId = opId ? highlightMatch(opId, query) : '';
            const highlightedMobile = mobile ? highlightMatch(mobile, query) : '';
            const highlightedEmail = email ? highlightMatch(email, query) : '';

            let details = [];
            if (mobile) details.push(`<span><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:2px; vertical-align: middle;"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>${highlightedMobile}</span>`);
            if (email) details.push(`<span><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:2px; vertical-align: middle;"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>${highlightedEmail}</span>`);
            if (nseit) details.push(`<span>NSEIT: ${highlightMatch(nseit, query)}</span>`);
            if (status) details.push(`<span style="color:#d97706; font-weight:600;">${escapeHtml(status)}</span>`);

            return `
                <div class="sc-item-header">
                    <span class="sc-item-title">${highlightedName}</span>
                    ${opId ? `<span class="sc-item-badge">${highlightedOpId}</span>` : ''}
                </div>
                ${details.length ? `<div class="sc-item-subtext">${details.join(' · ')}</div>` : ''}
            `;
        }

        _moveSelection(direction) {
            const items = this.dropdownMenu.querySelectorAll('.sc-dropdown-item');
            if (items.length === 0) return;

            if (this.selectedIndex >= 0 && items[this.selectedIndex]) {
                items[this.selectedIndex].classList.remove('is-focused');
            }

            this.selectedIndex += direction;
            if (this.selectedIndex >= items.length) this.selectedIndex = 0;
            if (this.selectedIndex < 0) this.selectedIndex = items.length - 1;

            const current = items[this.selectedIndex];
            if (current) {
                current.classList.add('is-focused');
                current.scrollIntoView({ block: 'nearest' });
            }
        }

        selectItem(item) {
            this.selectedItem = item;
            const displayName = item.station_id || item.new_station_id || item.name || item.operator_name || (typeof item === 'string' ? item : '');
            this.input.value = displayName;
            this.clearBtn.style.display = displayName ? 'flex' : 'none';
            this.close();

            if (typeof this.options.onSelect === 'function') {
                this.options.onSelect(item);
            }
        }

        clear() {
            this.input.value = '';
            this.selectedItem = null;
            this.clearBtn.style.display = 'none';
            if (typeof this.options.onClear === 'function') {
                this.options.onClear();
            }
        }

        setItems(newItems) {
            this.items = Array.isArray(newItems) ? [...newItems] : [];
            this.filteredItems = [...this.items];
            if (this.isOpen) {
                this._renderDropdown(this.input.value);
            }
        }

        open() {
            this.isOpen = true;
            this.wrapper.classList.add('is-open');
        }

        close() {
            this.isOpen = false;
            this.wrapper.classList.remove('is-open');
            this.selectedIndex = -1;
            const focused = this.dropdownMenu.querySelector('.is-focused');
            if (focused) focused.classList.remove('is-focused');
        }

        _setLoading(loading) {
            this.isLoading = loading;
            if (this.spinner) {
                this.spinner.style.display = loading ? 'inline-block' : 'none';
            }
        }

        destroy() {
            document.removeEventListener('click', this._outsideClickListener);
            if (this.container) {
                this.container.innerHTML = '';
            }
        }
    }

    return SearchableCombobox;
}));
