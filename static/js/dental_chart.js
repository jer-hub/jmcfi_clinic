/**
 * Interactive Dental Chart Component
 * Supports FDI notation, multi-select, surface-level marking, and data management
 */

class DentalChart {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Dental chart container not found:', containerId);
            return;
        }
        
        this.recordId = this.container.dataset.recordId;
        this.selectedTeeth = new Set();
        this.teethData = {};  // Use plain object for consistency with HTMX updates
        this.currentChartType = 'permanent';
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        
        this.init();
    }
    
    // Helper method to get tooth data - handles both Map and plain object
    getToothData(toothNumber) {
        const key = String(toothNumber);
        if (this.teethData instanceof Map) {
            return this.teethData.get(toothNumber) || this.teethData.get(key);
        }
        return this.teethData[key] || this.teethData[toothNumber];
    }
    
    // Helper method to check if tooth exists in data
    hasToothData(toothNumber) {
        const data = this.getToothData(toothNumber);
        return data && data.id;
    }
    
    async init() {
        this.bindEvents();
        await this.loadChartData();
        this.updateUI();
    }
    
    bindEvents() {
        // Tooth click events
        this.container.querySelectorAll('.tooth-wrapper').forEach(wrapper => {
            wrapper.addEventListener('click', (e) => this.handleToothClick(e, wrapper));
            wrapper.addEventListener('contextmenu', (e) => this.handleToothRightClick(e, wrapper));
            wrapper.addEventListener('mouseenter', (e) => this.showToothTooltip(e, wrapper));
            wrapper.addEventListener('mouseleave', () => this.hideToothTooltip());
        });
        
        // Surface click events
        this.container.querySelectorAll('.surface').forEach(surface => {
            surface.addEventListener('click', (e) => {
                e.stopPropagation();
                this.handleSurfaceClick(e, surface);
            });
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.clearSelection();
                this.closeAllModals();
            }
            if (e.key === 'Delete' && this.selectedTeeth.size > 0) {
                this.openBulkEditModal();
            }
        });
    }
    
    async loadChartData() {
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/`);
            if (!response.ok) throw new Error('Failed to load chart data');
            
            const data = await response.json();
            
            // Store teeth data as plain object for consistency
            this.teethData = {};
            data.teeth.forEach(tooth => {
                this.teethData[String(tooth.tooth_number)] = tooth;
            });
            
            this.applyTeethConditions();
        } catch (error) {
            console.error('Error loading chart data:', error);
            this.showToast('Failed to load dental chart data', 'error');
        }
    }
    
    // Alias for HTMX response compatibility
    renderChart() {
        this.applyTeethConditions();
    }
    
    applyTeethConditions() {
        // Reset all teeth
        this.container.querySelectorAll('.tooth').forEach(tooth => {
            tooth.className = tooth.className.replace(/condition-\w+/g, '').trim();
            tooth.classList.add('tooth');
            if (tooth.classList.contains('primary')) {
                tooth.classList.add('primary');
            } else {
                tooth.classList.add('permanent');
            }
        });
        
        // Handle both Map and plain object formats for teethData
        const entries = this.teethData instanceof Map 
            ? Array.from(this.teethData.entries())
            : Object.entries(this.teethData);
        
        // Apply conditions from data
        entries.forEach(([toothNumber, data]) => {
            const toothEl = document.getElementById(`tooth-${toothNumber}`);
            if (toothEl && data) {
                toothEl.classList.add(`condition-${data.condition}`);
                
                // Apply surface conditions
                if (data.surfaces && data.surfaces.length > 0) {
                    data.surfaces.forEach(surface => {
                        const surfaceEl = toothEl.querySelector(`[data-surface="${surface.surface}"]`);
                        if (surfaceEl) {
                            surfaceEl.className = surfaceEl.className.replace(/condition-\w+/g, '').trim();
                            surfaceEl.classList.add('surface', `surface-${surface.surface}`, `condition-${surface.condition}`);
                        }
                    });
                }
            }
        });
    }
    
    handleToothClick(e, wrapper) {
        const toothNumber = parseInt(wrapper.dataset.tooth);
        
        if (e.ctrlKey || e.metaKey) {
            // Multi-select mode
            this.toggleToothSelection(toothNumber, wrapper);
        } else if (e.shiftKey && this.selectedTeeth.size > 0) {
            // Range select mode
            this.selectRange(toothNumber);
        } else {
            // Single click - open edit modal
            this.clearSelection();
            this.openToothEditModal(toothNumber);
        }
    }
    
    handleToothRightClick(e, wrapper) {
        e.preventDefault();
        const toothNumber = parseInt(wrapper.dataset.tooth);
        
        // Quick action menu could be implemented here
        // For now, just select and open edit
        this.clearSelection();
        this.toggleToothSelection(toothNumber, wrapper);
        this.openToothEditModal(toothNumber);
    }
    
    handleSurfaceClick(e, surfaceEl) {
        const toothWrapper = surfaceEl.closest('.tooth-wrapper');
        const toothNumber = parseInt(toothWrapper.dataset.tooth);
        const surfaceName = surfaceEl.dataset.surface;
        
        // Check if tooth exists in data
        if (!this.hasToothData(toothNumber)) {
            this.showToast('Please mark the tooth first before editing surfaces', 'warning');
            return;
        }
        
        this.openSurfaceEditModal(toothNumber, surfaceName);
    }
    
    toggleToothSelection(toothNumber, wrapper) {
        if (this.selectedTeeth.has(toothNumber)) {
            this.selectedTeeth.delete(toothNumber);
            wrapper.classList.remove('selected');
        } else {
            this.selectedTeeth.add(toothNumber);
            wrapper.classList.add('selected');
        }
        this.updateSelectionUI();
    }
    
    selectRange(endTooth) {
        const startTooth = Math.min(...this.selectedTeeth);
        const quadrant = Math.floor(endTooth / 10);
        
        // Only select teeth in the same quadrant
        for (let i = Math.min(startTooth % 10, endTooth % 10); i <= Math.max(startTooth % 10, endTooth % 10); i++) {
            const toothNum = quadrant * 10 + i;
            const wrapper = this.container.querySelector(`[data-tooth="${toothNum}"]`);
            if (wrapper) {
                this.selectedTeeth.add(toothNum);
                wrapper.classList.add('selected');
            }
        }
        this.updateSelectionUI();
    }
    
    clearSelection() {
        this.selectedTeeth.clear();
        this.container.querySelectorAll('.tooth-wrapper.selected').forEach(el => {
            el.classList.remove('selected');
        });
        this.updateSelectionUI();
    }
    
    updateSelectionUI() {
        const count = this.selectedTeeth.size;
        const countEl = document.getElementById('selected-count');
        const bulkBtn = document.getElementById('bulk-edit-btn');
        
        if (countEl) countEl.textContent = count;
        if (bulkBtn) bulkBtn.disabled = count === 0;
    }
    
    showToothTooltip(e, wrapper) {
        const toothNumber = parseInt(wrapper.dataset.tooth);
        const tooltip = document.getElementById('tooth-tooltip');
        const content = document.getElementById('tooltip-content');
        
        if (!tooltip || !content) return;
        
        const data = this.teethData.get(toothNumber);
        const quadrant = Math.floor(toothNumber / 10);
        const position = toothNumber % 10;
        
        const quadrantNames = {
            1: 'Upper Right', 2: 'Upper Left',
            3: 'Lower Left', 4: 'Lower Right',
            5: 'Upper Right (Primary)', 6: 'Upper Left (Primary)',
            7: 'Lower Left (Primary)', 8: 'Lower Right (Primary)'
        };
        
        const toothNames = {
            1: 'Central Incisor', 2: 'Lateral Incisor', 3: 'Canine',
            4: 'First Premolar', 5: 'Second Premolar',
            6: 'First Molar', 7: 'Second Molar', 8: 'Third Molar'
        };
        
        const primaryToothNames = {
            1: 'Central Incisor', 2: 'Lateral Incisor', 3: 'Canine',
            4: 'First Molar', 5: 'Second Molar'
        };
        
        const isPrimary = quadrant >= 5;
        const toothName = isPrimary ? primaryToothNames[position] : toothNames[position];
        
        let html = `<strong>Tooth #${toothNumber}</strong><br>`;
        html += `${quadrantNames[quadrant]} - ${toothName || 'Unknown'}<br>`;
        
        if (data) {
            html += `<span class="text-yellow-300">Status: ${this.formatCondition(data.condition)}</span>`;
            if (data.notes) {
                html += `<br><em class="text-gray-300">${data.notes.substring(0, 50)}${data.notes.length > 50 ? '...' : ''}</em>`;
            }
        } else {
            html += `<span class="text-gray-400">No data recorded</span>`;
        }
        
        content.innerHTML = html;
        
        const rect = wrapper.getBoundingClientRect();
        tooltip.style.left = `${rect.left + rect.width / 2}px`;
        tooltip.style.top = `${rect.top - 10}px`;
        tooltip.style.transform = 'translate(-50%, -100%)';
        tooltip.classList.remove('hidden');
    }
    
    hideToothTooltip() {
        const tooltip = document.getElementById('tooth-tooltip');
        if (tooltip) tooltip.classList.add('hidden');
    }
    
    formatCondition(condition) {
        const conditionLabels = {
            'healthy': 'Healthy',
            'decayed': 'Decayed/Caries',
            'filled': 'Filled',
            'missing': 'Missing',
            'extracted': 'Extracted',
            'impacted': 'Impacted',
            'root_canal': 'Root Canal',
            'crowned': 'Crowned',
            'bridge': 'Bridge',
            'bridge_pontic': 'Bridge Pontic',
            'implant': 'Implant',
            'fractured': 'Fractured',
            'unerupted': 'Unerupted',
            'partially_erupted': 'Partially Erupted',
            'sealant': 'Sealant',
            'veneer': 'Veneer',
            'temporary': 'Temporary Filling',
            'root_fragment': 'Root Fragment',
            'anomaly': 'Anomaly',
            'other': 'Other'
        };
        return conditionLabels[condition] || condition;
    }
    
    // Modal Functions
    openToothEditModal(toothNumber) {
        const modal = document.getElementById('tooth-edit-modal');
        const form = document.getElementById('tooth-edit-form');
        const data = this.getToothData(toothNumber);
        const deleteBtn = document.getElementById('delete-tooth-btn');
        
        // Reset form surface selects first
        form.querySelectorAll('[name^="surface_"]').forEach(select => {
            select.value = '';
        });
        
        document.getElementById('edit-tooth-number').value = toothNumber;
        document.getElementById('edit-tooth-display').value = `Tooth #${toothNumber}`;
        document.getElementById('tooth-edit-title').textContent = `Edit Tooth #${toothNumber}`;
        
        if (data && data.id) {
            document.getElementById('edit-tooth-condition').value = data.condition;
            document.getElementById('edit-tooth-notes').value = data.notes || '';
            
            // Load surface conditions
            if (data.surfaces) {
                data.surfaces.forEach(s => {
                    const select = form.querySelector(`[name="surface_${s.surface}"]`);
                    if (select) select.value = s.condition;
                });
            }
            
            // Show delete button and set URL for existing tooth
            if (deleteBtn) {
                deleteBtn.classList.remove('hidden');
                deleteBtn.setAttribute('hx-delete', `/dental-records/${this.recordId}/chart/api/${data.id}/delete/`);
                // Re-process HTMX on the button
                if (typeof htmx !== 'undefined') {
                    htmx.process(deleteBtn);
                }
            }
        } else {
            document.getElementById('edit-tooth-condition').value = 'healthy';
            document.getElementById('edit-tooth-notes').value = '';
            form.querySelectorAll('[name^="surface_"]').forEach(select => {
                select.value = '';
            });
            
            // Hide delete button for new tooth
            if (deleteBtn) {
                deleteBtn.classList.add('hidden');
            }
        }
        
        modal.classList.remove('hidden');
    }
    
    closeToothEditModal() {
        document.getElementById('tooth-edit-modal').classList.add('hidden');
    }
    
    // HTMX handles the form submission now, but keeping this for fallback/legacy
    async saveToothEdit(e) {
        e.preventDefault();
        
        const toothNumber = parseInt(document.getElementById('edit-tooth-number').value);
        const condition = document.getElementById('edit-tooth-condition').value;
        const notes = document.getElementById('edit-tooth-notes').value;
        
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/update/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    tooth_number: toothNumber,
                    condition: condition,
                    notes: notes
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Update local data
                this.teethData.set(toothNumber, result.tooth);
                
                // Save surface conditions
                await this.saveSurfaceConditions(toothNumber, result.tooth.id);
                
                this.applyTeethConditions();
                this.closeToothEditModal();
                this.showToast(`Tooth #${toothNumber} saved successfully`, 'success');
                
                // Refresh the table
                this.refreshTeethTable();
            } else {
                this.showToast(result.error || 'Failed to save tooth', 'error');
            }
        } catch (error) {
            console.error('Error saving tooth:', error);
            this.showToast('Failed to save tooth data', 'error');
        }
    }
    
    async saveSurfaceConditions(toothNumber, toothId) {
        const form = document.getElementById('tooth-edit-form');
        const surfaces = ['mesial', 'distal', 'buccal', 'lingual', 'occlusal'];
        
        for (const surface of surfaces) {
            const select = form.querySelector(`[name="surface_${surface}"]`);
            if (select && select.value) {
                try {
                    await fetch(`/dental-records/${this.recordId}/chart/api/${toothId}/surface/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.csrfToken
                        },
                        body: JSON.stringify({
                            surface: surface,
                            condition: select.value
                        })
                    });
                } catch (error) {
                    console.error(`Error saving surface ${surface}:`, error);
                }
            }
        }
    }
    
    async deleteCurrentTooth() {
        const toothNumber = parseInt(document.getElementById('edit-tooth-number').value);
        const data = this.getToothData(toothNumber);
        
        if (!data || !data.id) {
            this.showToast('No data to delete for this tooth', 'warning');
            return;
        }
        
        if (!confirm(`Are you sure you want to delete Tooth #${toothNumber}?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/${data.id}/delete/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            
            if (response.ok) {
                delete this.teethData[String(toothNumber)];
                this.applyTeethConditions();
                this.closeToothEditModal();
                this.showToast(`Tooth #${toothNumber} deleted`, 'success');
                this.refreshTeethTable();
            } else {
                this.showToast('Failed to delete tooth', 'error');
            }
        } catch (error) {
            console.error('Error deleting tooth:', error);
            this.showToast('Failed to delete tooth data', 'error');
        }
    }
    
    openBulkEditModal() {
        if (this.selectedTeeth.size === 0) {
            this.showToast('Please select teeth first (Ctrl+Click)', 'warning');
            return;
        }
        
        const modal = document.getElementById('bulk-edit-modal');
        const teethList = document.getElementById('bulk-selected-teeth');
        const toothNumbersInput = document.getElementById('bulk-tooth-numbers');
        
        const sortedTeeth = Array.from(this.selectedTeeth).sort((a, b) => a - b);
        teethList.textContent = sortedTeeth.join(', ');
        
        // Set the hidden input with JSON array of tooth numbers for HTMX form submission
        if (toothNumbersInput) {
            toothNumbersInput.value = JSON.stringify(sortedTeeth);
        }
        
        modal.classList.remove('hidden');
    }
    
    closeBulkEditModal() {
        document.getElementById('bulk-edit-modal').classList.add('hidden');
    }
    
    async saveBulkEdit(e) {
        e.preventDefault();
        
        const condition = document.getElementById('bulk-condition').value;
        const notes = document.getElementById('bulk-notes').value;
        
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/bulk-update/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    tooth_numbers: Array.from(this.selectedTeeth),
                    condition: condition,
                    notes: notes
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast(`Updated ${result.updated_teeth.length} teeth`, 'success');
                await this.loadChartData();
                this.clearSelection();
                this.closeBulkEditModal();
                this.refreshTeethTable();
            } else {
                this.showToast(result.error || 'Failed to update teeth', 'error');
            }
        } catch (error) {
            console.error('Error bulk updating teeth:', error);
            this.showToast('Failed to update teeth', 'error');
        }
    }
    
    // Snapshot Functions
    async saveSnapshot() {
        const notes = prompt('Enter notes for this snapshot (optional):');
        
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/snapshots/save/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ notes: notes || '' })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Snapshot saved successfully', 'success');
            } else {
                this.showToast(result.error || 'Failed to save snapshot', 'error');
            }
        } catch (error) {
            console.error('Error saving snapshot:', error);
            this.showToast('Failed to save snapshot', 'error');
        }
    }
    
    async openSnapshotsModal() {
        const modal = document.getElementById('snapshots-modal');
        const list = document.getElementById('snapshots-list');
        
        modal.classList.remove('hidden');
        list.innerHTML = '<p class="text-gray-500 text-center py-4">Loading...</p>';
        
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/snapshots/`);
            const data = await response.json();
            
            if (data.snapshots.length === 0) {
                list.innerHTML = '<p class="text-gray-500 text-center py-4">No snapshots yet</p>';
            } else {
                list.innerHTML = data.snapshots.map(s => `
                    <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
                        <div class="flex justify-between items-start">
                            <div>
                                <div class="font-medium text-gray-800">${new Date(s.date).toLocaleString()}</div>
                                <div class="text-sm text-gray-500">By: ${s.created_by} | ${s.teeth_count} teeth recorded</div>
                                ${s.notes ? `<div class="text-sm text-gray-600 mt-1">${s.notes}</div>` : ''}
                            </div>
                            <button onclick="dentalChart.loadSnapshot(${s.id})" 
                                    class="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
                                Load
                            </button>
                        </div>
                    </div>
                `).join('');
            }
        } catch (error) {
            list.innerHTML = '<p class="text-red-500 text-center py-4">Failed to load snapshots</p>';
        }
    }
    
    closeSnapshotsModal() {
        document.getElementById('snapshots-modal').classList.add('hidden');
    }
    
    async loadSnapshot(snapshotId) {
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/snapshots/${snapshotId}/`);
            const data = await response.json();
            
            // Update local data with snapshot
            this.teethData.clear();
            data.chart_data.forEach(tooth => {
                this.teethData.set(tooth.tooth_number, tooth);
            });
            
            this.applyTeethConditions();
            this.closeSnapshotsModal();
            this.showToast('Snapshot loaded (view only - not saved)', 'info');
        } catch (error) {
            this.showToast('Failed to load snapshot', 'error');
        }
    }
    
    async openCompareModal() {
        const modal = document.getElementById('compare-modal');
        const select1 = document.getElementById('compare-snapshot1');
        const select2 = document.getElementById('compare-snapshot2');
        
        modal.classList.remove('hidden');
        
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/snapshots/`);
            const data = await response.json();
            
            const options = data.snapshots.map(s => 
                `<option value="${s.id}">${new Date(s.date).toLocaleDateString()} - ${s.notes || 'No notes'}</option>`
            ).join('');
            
            select1.innerHTML = '<option value="">Select snapshot...</option>' + options;
            select2.innerHTML = '<option value="">Select snapshot...</option>' + options;
        } catch (error) {
            this.showToast('Failed to load snapshots', 'error');
        }
    }
    
    closeCompareModal() {
        document.getElementById('compare-modal').classList.add('hidden');
        document.getElementById('comparison-results').classList.add('hidden');
    }
    
    async runComparison() {
        const id1 = document.getElementById('compare-snapshot1').value;
        const id2 = document.getElementById('compare-snapshot2').value;
        
        if (!id1 || !id2) {
            this.showToast('Please select both snapshots', 'warning');
            return;
        }
        
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/snapshots/compare/?snapshot1=${id1}&snapshot2=${id2}`);
            const data = await response.json();
            
            const resultsDiv = document.getElementById('comparison-results');
            const listDiv = document.getElementById('comparison-list');
            
            if (data.changes.length === 0) {
                listDiv.innerHTML = '<p class="text-gray-500">No changes found between these snapshots</p>';
            } else {
                listDiv.innerHTML = data.changes.map(c => {
                    let icon, text, color;
                    if (c.type === 'added') {
                        icon = 'plus-circle';
                        text = `Tooth #${c.tooth_number} added (${this.formatCondition(c.condition)})`;
                        color = 'green';
                    } else if (c.type === 'removed') {
                        icon = 'minus-circle';
                        text = `Tooth #${c.tooth_number} removed`;
                        color = 'red';
                    } else {
                        icon = 'exchange-alt';
                        text = `Tooth #${c.tooth_number}: ${this.formatCondition(c.from)} → ${this.formatCondition(c.to)}`;
                        color = 'blue';
                    }
                    return `<div class="flex items-center gap-2 p-2 bg-${color}-50 rounded text-${color}-700">
                        <i class="fas fa-${icon}"></i> ${text}
                    </div>`;
                }).join('');
            }
            
            resultsDiv.classList.remove('hidden');
        } catch (error) {
            this.showToast('Failed to compare snapshots', 'error');
        }
    }
    
    async exportChart() {
        try {
            const response = await fetch(`/dental-records/${this.recordId}/chart/api/export/`);
            const data = await response.json();
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dental_chart_${this.recordId}_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showToast('Chart exported successfully', 'success');
        } catch (error) {
            this.showToast('Failed to export chart', 'error');
        }
    }
    
    refreshTeethTable() {
        // Refresh the teeth table using HTMX or fetch
        const container = document.getElementById('teeth-table-container');
        if (container) {
            fetch(`/dental-records/${this.recordId}/chart/add/`, {
                method: 'GET',
                headers: {
                    'HX-Request': 'true'
                }
            }).then(response => {
                // The table will be refreshed on next load
                // For now, we just reload the section
                location.reload();
            }).catch(() => {
                // Silent fail - user can manually refresh
            });
        }
    }
    
    updateUI() {
        this.updateSelectionUI();
    }
    
    closeAllModals() {
        this.closeToothEditModal();
        this.closeBulkEditModal();
        this.closeSnapshotsModal();
        this.closeCompareModal();
    }
    
    showToast(message, type = 'info') {
        const colors = {
            success: 'bg-green-600',
            error: 'bg-red-600',
            warning: 'bg-yellow-600',
            info: 'bg-blue-600'
        };
        
        const toast = document.createElement('div');
        toast.className = `fixed top-20 right-4 z-50 px-6 py-3 ${colors[type]} text-white rounded-lg shadow-lg animate-fade-in`;
        toast.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'exclamation-circle' : 'info-circle'} mr-2"></i>${message}`;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('opacity-0', 'transition-opacity');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Global functions for template onclick handlers
let dentalChart = null;

function toggleChartType(type) {
    const permChart = document.getElementById('permanent-chart');
    const primChart = document.getElementById('primary-chart');
    const btnPerm = document.getElementById('btn-permanent');
    const btnPrim = document.getElementById('btn-primary');
    
    if (type === 'permanent') {
        permChart.classList.remove('hidden');
        primChart.classList.add('hidden');
        btnPerm.classList.add('bg-primary-600', 'text-white');
        btnPerm.classList.remove('text-gray-600');
        btnPrim.classList.remove('bg-primary-600', 'text-white');
        btnPrim.classList.add('text-gray-600');
    } else {
        permChart.classList.add('hidden');
        primChart.classList.remove('hidden');
        btnPrim.classList.add('bg-primary-600', 'text-white');
        btnPrim.classList.remove('text-gray-600');
        btnPerm.classList.remove('bg-primary-600', 'text-white');
        btnPerm.classList.add('text-gray-600');
    }
    
    if (dentalChart) {
        dentalChart.currentChartType = type;
        dentalChart.clearSelection();
    }
}

function clearSelection() {
    if (dentalChart) dentalChart.clearSelection();
}

function openBulkEditModal() {
    if (dentalChart) dentalChart.openBulkEditModal();
}

function closeBulkEditModal() {
    if (dentalChart) dentalChart.closeBulkEditModal();
}

function saveToothEdit(e) {
    if (dentalChart) dentalChart.saveToothEdit(e);
}

function closeToothEditModal() {
    if (dentalChart) dentalChart.closeToothEditModal();
}

function deleteCurrentTooth() {
    if (dentalChart) dentalChart.deleteCurrentTooth();
}

function saveBulkEdit(e) {
    if (dentalChart) dentalChart.saveBulkEdit(e);
}

function saveSnapshot() {
    if (dentalChart) dentalChart.saveSnapshot();
}

function openSnapshotsModal() {
    if (dentalChart) dentalChart.openSnapshotsModal();
}

function closeSnapshotsModal() {
    if (dentalChart) dentalChart.closeSnapshotsModal();
}

function openCompareModal() {
    if (dentalChart) dentalChart.openCompareModal();
}

function closeCompareModal() {
    if (dentalChart) dentalChart.closeCompareModal();
}

function runComparison() {
    if (dentalChart) dentalChart.runComparison();
}

function exportChart() {
    if (dentalChart) dentalChart.exportChart();
}

// Helper function for HTMX bulk edit form - returns additional values
function getBulkFormValues() {
    if (!dentalChart) return {};
    const sortedTeeth = Array.from(dentalChart.selectedTeeth).sort((a, b) => a - b);
    return {
        tooth_numbers_json: JSON.stringify(sortedTeeth)
    };
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    const chartContainer = document.getElementById('interactive-dental-chart');
    if (chartContainer) {
        dentalChart = new DentalChart('interactive-dental-chart');
    }
});
