document.addEventListener('DOMContentLoaded', () => {
    initTableSorting();
    
    // Use MutationObserver to catch dynamically added tables (e.g. report previews)
    const observer = new MutationObserver((mutations) => {
        let shouldInit = false;
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length) {
                shouldInit = true;
            }
        });
        if (shouldInit) {
            initTableSorting();
        }
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
});

function initTableSorting() {
    // Target tables that likely contain data we want to sort
    const tables = document.querySelectorAll('table.preview-table, table.mon-table, table.dataframe, table.data-table');
    
    tables.forEach(table => {
        // Prevent double initialization
        if (table.hasAttribute('data-sort-initialized')) return;
        table.setAttribute('data-sort-initialized', 'true');
        
        const headers = table.querySelectorAll('thead th');
        if (headers.length === 0) return;
        
        headers.forEach((th, colIndex) => {
            // Don't add to empty headers
            if (!th.textContent.trim()) return;
            
            // Make header clickable
            th.style.cursor = 'pointer';
            th.style.userSelect = 'none';
            th.style.position = 'relative';
            
            // Avoid adding multiple icons if DOM changed
            if (!th.querySelector('.sort-icon')) {
                const icon = document.createElement('i');
                icon.className = 'ti ti-arrows-sort sort-icon';
                icon.style.marginLeft = '6px';
                icon.style.fontSize = '14px';
                icon.style.opacity = '0.5';
                icon.style.verticalAlign = 'middle';
                th.appendChild(icon);
            }
            
            let sortAsc = true;
            
            th.addEventListener('click', () => {
                const tbody = table.querySelector('tbody') || table;
                const rows = Array.from(tbody.querySelectorAll('tr'));
                // Exclude header rows and total count rows from sorting
                const dataRows = rows.filter(row => !row.querySelector('th') && !row.classList.contains('total-row') && !row.closest('tfoot'));
                
                // Tag originalIndex for reset functionality if not present
                dataRows.forEach((row, idx) => {
                    if (row.dataset.originalIndex === undefined) {
                        row.dataset.originalIndex = idx;
                    }
                });
                
                // Determine if column is numeric
                let isNumeric = true;
                for (let i = 0; i < Math.min(dataRows.length, 10); i++) {
                    let cell = dataRows[i].children[colIndex];
                    if (cell) {
                        let text = cell.textContent.trim().replace(/,/g, '').replace(/%/g, '');
                        if (text !== '' && text !== '-' && isNaN(Number(text))) {
                            isNumeric = false;
                            break;
                        }
                    }
                }
                
                // Sort rows
                dataRows.sort((a, b) => {
                    let aCol = a.children[colIndex];
                    let bCol = b.children[colIndex];
                    let aText = aCol ? aCol.textContent.trim() : '';
                    let bText = bCol ? bCol.textContent.trim() : '';
                    
                    if (isNumeric) {
                        let aVal = parseFloat(aText.replace(/,/g, '').replace(/%/g, ''));
                        let bVal = parseFloat(bText.replace(/,/g, '').replace(/%/g, ''));
                        if (isNaN(aVal)) aVal = -Infinity;
                        if (isNaN(bVal)) bVal = -Infinity;
                        return sortAsc ? aVal - bVal : bVal - aVal;
                    } else {
                        return sortAsc ? aText.localeCompare(bText) : bText.localeCompare(aText);
                    }
                });
                
                // Re-append rows
                dataRows.forEach(row => tbody.appendChild(row));
                
                // Reset icons
                headers.forEach(h => {
                    const i = h.querySelector('.sort-icon');
                    if (i) {
                        i.className = 'ti ti-arrows-sort sort-icon';
                        i.style.opacity = '0.5';
                        i.style.color = 'inherit';
                    }
                });
                
                // Set active icon
                const activeIcon = th.querySelector('.sort-icon');
                if (activeIcon) {
                    activeIcon.className = sortAsc ? 'ti ti-sort-ascending sort-icon' : 'ti ti-sort-descending sort-icon';
                    activeIcon.style.opacity = '1';
                    activeIcon.style.color = '#3b82f6';
                }
                
                sortAsc = !sortAsc;
            });
        });
    });
}
