document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const createBackupBtn = document.getElementById('createBackupBtn');
    const backupTableBody = document.querySelector('#backupTable tbody');
    const restoreModal = new bootstrap.Modal(document.getElementById('restoreModal'));
    const confirmRestoreBtn = document.getElementById('confirmRestoreBtn');
    
    // Variables de estado
    let selectedBackup = null;

    // Event Listeners
    if (createBackupBtn) {
        createBackupBtn.addEventListener('click', handleCreateBackup);
    }
    
    if (confirmRestoreBtn) {
        confirmRestoreBtn.addEventListener('click', handleRestoreBackup);
    }

    // Delegación de eventos para botones dinámicos
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('download-btn')) {
            const filename = e.target.dataset.filename;
            downloadBackup(filename);
        }
        
        if (e.target.classList.contains('restore-btn')) {
            selectedBackup = e.target.dataset.filename;
            restoreModal.show();
        }
    });

    // Cargar backups al iniciar
    loadBackups();

    // Funciones principales
    async function loadBackups() {
        try {
            const response = await fetch('/backup/api/list');
            const data = await response.json();

            if (data.success && Array.isArray(data.data)) {
                renderBackups(data.data);
            } else {
                console.error('Formato de respuesta inesperado:', data);
                showAlert('Error en formato de respuesta', 'danger');
            }
        } catch (error) {
            console.error('Error al cargar backups:', error);
            showAlert('Error al cargar respaldos', 'danger');
        }
    }

    function renderBackups(backups) {
        if (!backupTableBody) return;
        
        backupTableBody.innerHTML = '';
        
        if (backups.length === 0) {
            backupTableBody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center">No se encontraron respaldos</td>
                </tr>
            `;
            return;
        }
        
        backups.forEach(backup => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${backup.filename}</td>
                <td>${backup.size}</td>
                <td>${backup.created}</td>
                <td>
                    <button class="btn btn-sm btn-info download-btn" data-filename="${backup.filename}">
                        <i class="fas fa-download"></i> Descargar
                    </button>
                    <button class="btn btn-sm btn-warning restore-btn" data-filename="${backup.filename}">
                        <i class="fas fa-undo"></i> Restaurar
                    </button>
                </td>
            `;
            backupTableBody.appendChild(row);
        });
    }

    async function handleCreateBackup() {
        if (!createBackupBtn) return;
        
        try {
            // Cambiar estado del botón
            createBackupBtn.disabled = true;
            createBackupBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creando...';
            
            const response = await fetch('/backup/api/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('Respaldo creado exitosamente', 'success');
                await loadBackups(); // Recargar la lista
            } else {
                throw new Error(result.message || 'Error desconocido');
            }
        } catch (error) {
            console.error('Error al crear respaldo:', error);
            showAlert(`Error: ${error.message}`, 'danger');
        } finally {
            if (createBackupBtn) {
                createBackupBtn.disabled = false;
                createBackupBtn.innerHTML = '<i class="fas fa-plus-circle"></i> Crear Respaldo';
            }
        }
    }

    function downloadBackup(filename) {
        window.location.href = `/backup/api/download/${encodeURIComponent(filename)}`;
    }

    async function handleRestoreBackup() {
        if (!selectedBackup || !confirmRestoreBtn) return;
        
        try {
            confirmRestoreBtn.disabled = true;
            confirmRestoreBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restaurando...';
            
            const response = await fetch(`/backup/api/restore/${encodeURIComponent(selectedBackup)}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert(`Base de datos restaurada. Respaldo preventivo: ${result.preventive_backup}`, 'success');
                await loadBackups(); // Recargar la lista
            } else {
                throw new Error(result.message || 'Error desconocido');
            }
        } catch (error) {
            console.error('Error al restaurar:', error);
            showAlert(`Error al restaurar: ${error.message}`, 'danger');
        } finally {
            restoreModal.hide();
            if (confirmRestoreBtn) {
                confirmRestoreBtn.disabled = false;
                confirmRestoreBtn.innerHTML = '<i class="fas fa-undo"></i> Restaurar';
            }
            selectedBackup = null;
        }
    }

    // Función auxiliar para mostrar alertas
    function showAlert(message, type) {
        const alertsContainer = document.getElementById('alertsContainer') || document.body;
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.role = 'alert';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertsContainer.prepend(alert);
        
        // Auto-eliminar después de 5 segundos
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 150);
        }, 5000);
    }
});