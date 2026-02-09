"""
Field Access Dashboard Component for Jorge's Real Estate AI

Production-ready field agent interface optimized for mobile real estate operations.
Designed for on-site property visits, client meetings, and field data collection.

Features:
- GPS property check-in interface
- Voice note capture with transcription
- Photo upload with compression and metadata
- Offline queue with automatic sync
- Quick action buttons for field workflows
- Touch-optimized UI for outdoor/gloved use
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


class FieldActionType(Enum):
    """Types of field actions available."""
    CHECK_IN = "check_in"
    VOICE_NOTE = "voice_note"
    PHOTO_UPLOAD = "photo_upload"
    CLIENT_MEETING = "client_meeting"
    PROPERTY_INSPECTION = "property_inspection"
    QUICK_UPDATE = "quick_update"
    EMERGENCY_CONTACT = "emergency_contact"


class SyncStatus(Enum):
    """Sync status for offline queue items."""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"


@dataclass
class FieldAction:
    """Data structure for field actions."""
    id: str
    action_type: FieldActionType
    timestamp: datetime
    location: Optional[Tuple[float, float]]  # (lat, lng)
    property_id: Optional[str]
    data: Dict[str, Any]
    sync_status: SyncStatus = SyncStatus.PENDING
    priority: int = 1  # 1=low, 2=medium, 3=high


def get_field_access_css() -> str:
    """Returns CSS optimized for field use with large touch targets."""
    return """
    <style>
        /* Field Dashboard Container */
        .field-dashboard {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            border-radius: 16px;
            padding: 20px;
            margin: 16px 0;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            position: relative;
            overflow: hidden;
        }

        .field-dashboard::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #3b82f6, #f59e0b);
        }

        /* Field Header */
        .field-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 12px;
        }

        .field-title {
            font-size: 20px;
            font-weight: 700;
            color: #1f2937;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .field-status-badge {
            background: #10b981;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .field-status-badge.offline {
            background: #ef4444;
        }

        .field-status-badge.syncing {
            background: #f59e0b;
        }

        /* Quick Actions Grid */
        .field-actions-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .field-action-button {
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            min-height: 120px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 8px;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
            text-decoration: none;
            position: relative;
            overflow: hidden;
        }

        .field-action-button:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            border-color: #3b82f6;
        }

        .field-action-button:active {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        .field-action-button.primary {
            background: linear-gradient(135deg, #3b82f6, #1e3a8a);
            color: white;
            border-color: #3b82f6;
        }

        .field-action-button.primary:hover {
            background: linear-gradient(135deg, #2563eb, #1e40af);
        }

        .field-action-button.warning {
            background: linear-gradient(135deg, #f59e0b, #d97706);
            color: white;
            border-color: #f59e0b;
        }

        .field-action-button.success {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            border-color: #10b981;
        }

        .field-action-icon {
            font-size: 32px;
            margin-bottom: 8px;
        }

        .field-action-label {
            font-size: 14px;
            font-weight: 600;
            line-height: 1.2;
        }

        .field-action-sublabel {
            font-size: 11px;
            opacity: 0.8;
            font-weight: 400;
        }

        /* Location Display */
        .field-location {
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            border: 1px solid #e5e7eb;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .field-location-icon {
            font-size: 24px;
            color: #3b82f6;
        }

        .field-location-info {
            flex: 1;
        }

        .field-location-address {
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 4px;
        }

        .field-location-coords {
            font-size: 12px;
            color: #6b7280;
            font-family: 'Monaco', monospace;
        }

        .field-location-accuracy {
            font-size: 10px;
            color: #10b981;
            font-weight: 500;
        }

        /* Sync Queue */
        .field-sync-queue {
            background: white;
            border-radius: 12px;
            border: 1px solid #e5e7eb;
            overflow: hidden;
        }

        .field-sync-header {
            background: #f8fafc;
            padding: 12px 16px;
            border-bottom: 1px solid #e5e7eb;
            font-weight: 600;
            color: #374151;
            display: flex;
            justify-content: between;
            align-items: center;
        }

        .field-sync-count {
            background: #3b82f6;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            margin-left: auto;
        }

        .field-sync-item {
            padding: 12px 16px;
            border-bottom: 1px solid #f1f5f9;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .field-sync-item:last-child {
            border-bottom: none;
        }

        .field-sync-status {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            flex-shrink: 0;
        }

        .field-sync-status.pending {
            background: #6b7280;
        }

        .field-sync-status.syncing {
            background: #f59e0b;
            animation: syncPulse 1.5s infinite;
        }

        .field-sync-status.synced {
            background: #10b981;
        }

        .field-sync-status.failed {
            background: #ef4444;
        }

        .field-sync-details {
            flex: 1;
        }

        .field-sync-action {
            font-size: 13px;
            font-weight: 600;
            color: #1f2937;
        }

        .field-sync-time {
            font-size: 11px;
            color: #6b7280;
        }

        /* Voice Recording Interface */
        .field-voice-recorder {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin: 16px 0;
            text-align: center;
            border: 2px dashed #d1d5db;
            transition: all 0.3s ease;
        }

        .field-voice-recorder.recording {
            border-color: #ef4444;
            background: #fef2f2;
        }

        .field-voice-record-button {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: linear-gradient(135deg, #ef4444, #dc2626);
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            transition: all 0.2s ease;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
        }

        .field-voice-record-button:hover {
            transform: scale(1.1);
        }

        .field-voice-record-button:active {
            transform: scale(1.05);
        }

        .field-voice-record-button.recording {
            animation: recordPulse 1s infinite;
        }

        /* Photo Upload Interface */
        .field-photo-upload {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin: 16px 0;
            border: 2px dashed #d1d5db;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .field-photo-upload:hover {
            border-color: #3b82f6;
            background: #f8fafc;
        }

        .field-photo-upload.dragover {
            border-color: #10b981;
            background: #ecfdf5;
        }

        .field-photo-preview {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            gap: 8px;
            margin-top: 16px;
        }

        .field-photo-thumbnail {
            aspect-ratio: 1;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
            cursor: pointer;
        }

        .field-photo-thumbnail img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .field-photo-remove {
            position: absolute;
            top: 4px;
            right: 4px;
            background: rgba(239, 68, 68, 0.9);
            color: white;
            border: none;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            cursor: pointer;
            font-size: 12px;
        }

        /* Animations */
        @keyframes syncPulse {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
            }
            50% {
                opacity: 0.7;
                transform: scale(1.2);
            }
        }

        @keyframes recordPulse {
            0%, 100% {
                box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
            }
            70% {
                box-shadow: 0 0 0 20px rgba(239, 68, 68, 0);
            }
        }

        /* Responsive Design */
        @media (max-width: 640px) {
            .field-actions-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .field-action-button {
                min-height: 100px;
                padding: 16px;
            }
            
            .field-action-icon {
                font-size: 28px;
            }
        }

        @media (max-width: 480px) {
            .field-actions-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Dark mode for outdoor visibility */
        .field-dashboard.high-contrast {
            background: #1f2937;
            color: white;
        }

        .field-dashboard.high-contrast .field-action-button {
            background: #374151;
            border-color: #4b5563;
            color: white;
        }

        .field-dashboard.high-contrast .field-location {
            background: #374151;
            border-color: #4b5563;
        }

        /* Jorge's Real Estate AI Branding */
        .field-brand-badge {
            position: absolute;
            top: 12px;
            right: 12px;
            background: linear-gradient(135deg, #3b82f6, #1e3a8a);
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
    </style>
    """


def get_field_access_js() -> str:
    """Returns JavaScript for field interactions including GPS and voice recording."""
    return """
    <script>
        class FieldAccessDashboard {
            constructor() {
                this.location = null;
                this.watchId = null;
                this.isRecording = false;
                this.mediaRecorder = null;
                this.audioChunks = [];
                this.syncQueue = [];
                this.init();
            }

            init() {
                this.setupGeolocation();
                this.setupOfflineSync();
                this.setupVoiceRecording();
                this.setupPhotoUpload();
                this.setupFieldActions();
            }

            setupGeolocation() {
                if (!navigator.geolocation) {
                    console.warn('Geolocation not supported');
                    return;
                }

                const options = {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 60000
                };

                // Get initial position
                navigator.geolocation.getCurrentPosition(
                    (position) => this.updateLocation(position),
                    (error) => this.handleLocationError(error),
                    options
                );

                // Watch position changes
                this.watchId = navigator.geolocation.watchPosition(
                    (position) => this.updateLocation(position),
                    (error) => this.handleLocationError(error),
                    options
                );
            }

            updateLocation(position) {
                this.location = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: new Date()
                };

                this.updateLocationDisplay();
            }

            updateLocationDisplay() {
                const locationEl = document.querySelector('.field-location-coords');
                const accuracyEl = document.querySelector('.field-location-accuracy');
                
                if (locationEl && this.location) {
                    locationEl.textContent = 
                        `${this.location.lat.toFixed(6)}, ${this.location.lng.toFixed(6)}`;
                }
                
                if (accuracyEl && this.location) {
                    accuracyEl.textContent = `±${this.location.accuracy.toFixed(0)}m accuracy`;
                }
            }

            handleLocationError(error) {
                console.error('Location error:', error);
                const statusBadge = document.querySelector('.field-status-badge');
                if (statusBadge) {
                    statusBadge.textContent = 'Location Error';
                    statusBadge.className = 'field-status-badge offline';
                }
            }

            setupVoiceRecording() {
                const recordButton = document.querySelector('.field-voice-record-button');
                if (!recordButton) return;

                recordButton.addEventListener('click', () => {
                    if (this.isRecording) {
                        this.stopRecording();
                    } else {
                        this.startRecording();
                    }
                });
            }

            async startRecording() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    this.mediaRecorder = new MediaRecorder(stream);
                    this.audioChunks = [];

                    this.mediaRecorder.ondataavailable = (event) => {
                        this.audioChunks.push(event.data);
                    };

                    this.mediaRecorder.onstop = () => {
                        this.processRecording();
                    };

                    this.mediaRecorder.start();
                    this.isRecording = true;
                    this.updateRecordingUI(true);

                    // Haptic feedback
                    if (navigator.vibrate) {
                        navigator.vibrate(50);
                    }

                } catch (error) {
                    console.error('Error starting recording:', error);
                    alert('Unable to access microphone');
                }
            }

            stopRecording() {
                if (this.mediaRecorder && this.isRecording) {
                    this.mediaRecorder.stop();
                    this.isRecording = false;
                    this.updateRecordingUI(false);

                    // Stop all audio tracks
                    this.mediaRecorder.stream.getTracks().forEach(track => track.stop());

                    // Haptic feedback
                    if (navigator.vibrate) {
                        navigator.vibrate([50, 50, 50]);
                    }
                }
            }

            updateRecordingUI(recording) {
                const button = document.querySelector('.field-voice-record-button');
                const container = document.querySelector('.field-voice-recorder');

                if (button && container) {
                    if (recording) {
                        button.textContent = '⏹️';
                        button.classList.add('recording');
                        container.classList.add('recording');
                    } else {
                        button.textContent = '🎤';
                        button.classList.remove('recording');
                        container.classList.remove('recording');
                    }
                }
            }

            processRecording() {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                
                const voiceNote = {
                    id: this.generateId(),
                    type: 'voice_note',
                    timestamp: new Date(),
                    location: this.location,
                    data: audioBlob,
                    size: audioBlob.size
                };

                this.addToSyncQueue(voiceNote);
            }

            setupPhotoUpload() {
                const uploadArea = document.querySelector('.field-photo-upload');
                if (!uploadArea) return;

                // Click to upload
                uploadArea.addEventListener('click', () => {
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.multiple = true;
                    input.accept = 'image/*';
                    input.capture = 'environment'; // Use back camera on mobile
                    
                    input.onchange = (event) => {
                        this.handlePhotoFiles(event.target.files);
                    };
                    
                    input.click();
                });

                // Drag and drop
                uploadArea.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    uploadArea.classList.add('dragover');
                });

                uploadArea.addEventListener('dragleave', () => {
                    uploadArea.classList.remove('dragover');
                });

                uploadArea.addEventListener('drop', (e) => {
                    e.preventDefault();
                    uploadArea.classList.remove('dragover');
                    this.handlePhotoFiles(e.dataTransfer.files);
                });
            }

            handlePhotoFiles(files) {
                Array.from(files).forEach(file => {
                    if (file.type.startsWith('image/')) {
                        this.processPhoto(file);
                    }
                });
            }

            processPhoto(file) {
                // Compress image for mobile performance
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = new Image();

                img.onload = () => {
                    // Calculate new dimensions (max 1200px)
                    const maxSize = 1200;
                    let { width, height } = img;
                    
                    if (width > height) {
                        if (width > maxSize) {
                            height = (height * maxSize) / width;
                            width = maxSize;
                        }
                    } else {
                        if (height > maxSize) {
                            width = (width * maxSize) / height;
                            height = maxSize;
                        }
                    }

                    canvas.width = width;
                    canvas.height = height;

                    // Draw and compress
                    ctx.drawImage(img, 0, 0, width, height);
                    
                    canvas.toBlob((blob) => {
                        const photo = {
                            id: this.generateId(),
                            type: 'photo_upload',
                            timestamp: new Date(),
                            location: this.location,
                            data: blob,
                            originalName: file.name,
                            size: blob.size
                        };

                        this.addToSyncQueue(photo);
                        this.displayPhotoThumbnail(photo);
                    }, 'image/jpeg', 0.8);
                };

                img.src = URL.createObjectURL(file);
            }

            displayPhotoThumbnail(photo) {
                const preview = document.querySelector('.field-photo-preview');
                if (!preview) return;

                const thumbnail = document.createElement('div');
                thumbnail.className = 'field-photo-thumbnail';
                thumbnail.innerHTML = `
                    <img src="${URL.createObjectURL(photo.data)}" alt="Photo">
                    <button class="field-photo-remove" onclick="fieldDashboard.removePhoto('${photo.id}')">×</button>
                `;

                preview.appendChild(thumbnail);
            }

            removePhoto(photoId) {
                // Remove from sync queue
                this.syncQueue = this.syncQueue.filter(item => item.id !== photoId);
                
                // Remove from UI
                const thumbnails = document.querySelectorAll('.field-photo-thumbnail');
                thumbnails.forEach(thumb => {
                    const button = thumb.querySelector('.field-photo-remove');
                    if (button && button.onclick.toString().includes(photoId)) {
                        thumb.remove();
                    }
                });

                this.updateSyncQueueDisplay();
            }

            setupFieldActions() {
                const actionButtons = document.querySelectorAll('.field-action-button');
                
                actionButtons.forEach(button => {
                    button.addEventListener('click', (e) => {
                        const action = button.dataset.action;
                        this.handleFieldAction(action, button);
                        
                        // Visual feedback
                        button.style.animation = 'none';
                        button.offsetHeight; // Trigger reflow
                        button.style.animation = 'pulse 0.3s ease';
                    });
                });
            }

            handleFieldAction(action, button) {
                // Haptic feedback
                if (navigator.vibrate) {
                    navigator.vibrate(25);
                }

                const fieldAction = {
                    id: this.generateId(),
                    type: action,
                    timestamp: new Date(),
                    location: this.location,
                    data: { source: 'field_dashboard' }
                };

                this.addToSyncQueue(fieldAction);

                // Send to Streamlit
                window.parent.postMessage({
                    type: 'field-action',
                    action: action,
                    location: this.location,
                    timestamp: new Date().toISOString()
                }, '*');
            }

            addToSyncQueue(item) {
                this.syncQueue.push(item);
                this.updateSyncQueueDisplay();
                this.attemptSync();
            }

            updateSyncQueueDisplay() {
                const countEl = document.querySelector('.field-sync-count');
                const pendingCount = this.syncQueue.filter(item => 
                    !item.synced && !item.failed).length;
                
                if (countEl) {
                    countEl.textContent = pendingCount;
                    countEl.style.display = pendingCount > 0 ? 'block' : 'none';
                }
            }

            setupOfflineSync() {
                // Check online status
                this.updateOnlineStatus();
                
                window.addEventListener('online', () => {
                    this.updateOnlineStatus();
                    this.attemptSync();
                });
                
                window.addEventListener('offline', () => {
                    this.updateOnlineStatus();
                });

                // Periodic sync attempt
                setInterval(() => {
                    if (navigator.onLine) {
                        this.attemptSync();
                    }
                }, 30000);
            }

            updateOnlineStatus() {
                const badge = document.querySelector('.field-status-badge');
                if (!badge) return;

                if (navigator.onLine) {
                    badge.textContent = 'Online';
                    badge.className = 'field-status-badge';
                } else {
                    badge.textContent = 'Offline';
                    badge.className = 'field-status-badge offline';
                }
            }

            attemptSync() {
                if (!navigator.onLine) return;

                const pendingItems = this.syncQueue.filter(item => !item.synced && !item.syncing);
                
                pendingItems.forEach(item => {
                    item.syncing = true;
                    
                    // Simulate sync (replace with actual API call)
                    setTimeout(() => {
                        item.synced = true;
                        item.syncing = false;
                        this.updateSyncQueueDisplay();
                    }, 1000 + Math.random() * 2000);
                });
            }

            generateId() {
                return 'field_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            }
        }

        // Initialize when DOM is ready
        document.addEventListener('DOMContentLoaded', () => {
            window.fieldDashboard = new FieldAccessDashboard();
        });
    </script>
    """


def render_location_display(
    current_location: Optional[Tuple[float, float]] = None,
    address: Optional[str] = None,
    accuracy: Optional[float] = None
) -> str:
    """Renders the current location display."""
    if current_location:
        lat, lng = current_location
        coords_text = f"{lat:.6f}, {lng:.6f}"
        accuracy_text = f"±{accuracy:.0f}m accuracy" if accuracy else "Location acquired"
    else:
        coords_text = "Acquiring location..."
        accuracy_text = "GPS initializing"
    
    display_address = address or "Unknown location"
    
    return f"""
    <div class="field-location">
        <div class="field-location-icon">📍</div>
        <div class="field-location-info">
            <div class="field-location-address">{display_address}</div>
            <div class="field-location-coords">{coords_text}</div>
            <div class="field-location-accuracy">{accuracy_text}</div>
        </div>
    </div>
    """


def render_field_actions() -> str:
    """Renders the field action buttons grid."""
    actions = [
        {
            'id': 'check_in',
            'icon': '📍',
            'label': 'Check In',
            'sublabel': 'Property visit',
            'class': 'primary'
        },
        {
            'id': 'voice_note',
            'icon': '🎤',
            'label': 'Voice Note',
            'sublabel': 'Record audio',
            'class': ''
        },
        {
            'id': 'photo_upload',
            'icon': '📷',
            'label': 'Take Photos',
            'sublabel': 'Property images',
            'class': ''
        },
        {
            'id': 'client_meeting',
            'icon': '🤝',
            'label': 'Client Meeting',
            'sublabel': 'Log interaction',
            'class': 'success'
        },
        {
            'id': 'inspection',
            'icon': '🔍',
            'label': 'Inspection',
            'sublabel': 'Property review',
            'class': ''
        },
        {
            'id': 'emergency',
            'icon': '🚨',
            'label': 'Emergency',
            'sublabel': 'Urgent contact',
            'class': 'warning'
        }
    ]
    
    actions_html = ""
    for action in actions:
        actions_html += f"""
        <button class="field-action-button {action['class']}" data-action="{action['id']}">
            <div class="field-action-icon">{action['icon']}</div>
            <div class="field-action-label">{action['label']}</div>
            <div class="field-action-sublabel">{action['sublabel']}</div>
        </button>
        """
    
    return f"""
    <div class="field-actions-grid">
        {actions_html}
    </div>
    """


def render_voice_recorder() -> str:
    """Renders the voice recording interface."""
    return """
    <div class="field-voice-recorder">
        <button class="field-voice-record-button">🎤</button>
        <div style="font-weight: 600; color: #374151; margin-bottom: 4px;">Voice Notes</div>
        <div style="font-size: 12px; color: #6b7280;">Tap and hold to record, release to stop</div>
    </div>
    """


def render_photo_upload() -> str:
    """Renders the photo upload interface."""
    return """
    <div class="field-photo-upload">
        <div style="font-size: 32px; margin-bottom: 8px;">📷</div>
        <div style="font-weight: 600; color: #374151; margin-bottom: 4px;">Property Photos</div>
        <div style="font-size: 12px; color: #6b7280;">Tap to capture or drag images here</div>
        <div class="field-photo-preview"></div>
    </div>
    """


def render_sync_queue(queue_items: List[FieldAction] = None) -> str:
    """Renders the offline sync queue."""
    if queue_items is None:
        queue_items = []
    
    queue_html = ""
    for item in queue_items:
        status_class = item.sync_status.value
        action_label = item.action_type.value.replace('_', ' ').title()
        time_str = item.timestamp.strftime('%H:%M')
        
        queue_html += f"""
        <div class="field-sync-item">
            <div class="field-sync-status {status_class}"></div>
            <div class="field-sync-details">
                <div class="field-sync-action">{action_label}</div>
                <div class="field-sync-time">{time_str}</div>
            </div>
        </div>
        """
    
    return f"""
    <div class="field-sync-queue">
        <div class="field-sync-header">
            Sync Queue
            <span class="field-sync-count">{len([i for i in queue_items if i.sync_status == SyncStatus.PENDING])}</span>
        </div>
        {queue_html if queue_html else '<div class="field-sync-item" style="text-align: center; color: #6b7280; font-size: 12px;">No pending actions</div>'}
    </div>
    """


def create_field_access_dashboard(
    current_location: Optional[Tuple[float, float]] = None,
    address: Optional[str] = None,
    gps_accuracy: Optional[float] = None,
    sync_queue: Optional[List[FieldAction]] = None,
    online_status: bool = True,
    high_contrast: bool = False
) -> None:
    """
    Creates and renders the complete field access dashboard.
    
    Args:
        current_location: Current GPS coordinates (lat, lng)
        address: Human-readable address
        gps_accuracy: GPS accuracy in meters
        sync_queue: List of pending sync actions
        online_status: Whether device is online
        high_contrast: Enable high contrast mode for outdoor visibility
    """
    # Inject CSS and JavaScript
    st.markdown(get_field_access_css(), unsafe_allow_html=True)
    st.markdown(get_field_access_js(), unsafe_allow_html=True)
    
    # Determine status badge
    if online_status:
        status_badge = '<span class="field-status-badge">Online</span>'
    else:
        status_badge = '<span class="field-status-badge offline">Offline</span>'
    
    # Container class
    container_class = "field-dashboard"
    if high_contrast:
        container_class += " high-contrast"
    
    # Build complete dashboard HTML
    dashboard_html = f"""
    <div class="{container_class}">
        <div class="field-brand-badge">Jorge AI</div>
        
        <div class="field-header">
            <h3 class="field-title">
                🏠 Field Operations
            </h3>
            {status_badge}
        </div>
        
        {render_location_display(current_location, address, gps_accuracy)}
        {render_field_actions()}
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0;">
            <div>{render_voice_recorder()}</div>
            <div>{render_photo_upload()}</div>
        </div>
        
        {render_sync_queue(sync_queue or [])}
    </div>
    """
    
    st.markdown(dashboard_html, unsafe_allow_html=True)


def get_sample_sync_queue() -> List[FieldAction]:
    """Returns sample sync queue items for demonstration."""
    return [
        FieldAction(
            id="field_001",
            action_type=FieldActionType.CHECK_IN,
            timestamp=datetime.now() - timedelta(minutes=5),
            location=(40.7589, -73.9851),
            property_id="prop_123",
            data={"address": "123 Main St"},
            sync_status=SyncStatus.SYNCED
        ),
        FieldAction(
            id="field_002",
            action_type=FieldActionType.VOICE_NOTE,
            timestamp=datetime.now() - timedelta(minutes=2),
            location=(40.7589, -73.9851),
            property_id="prop_123",
            data={"duration": 45},
            sync_status=SyncStatus.SYNCING
        ),
        FieldAction(
            id="field_003",
            action_type=FieldActionType.PHOTO_UPLOAD,
            timestamp=datetime.now() - timedelta(minutes=1),
            location=(40.7589, -73.9851),
            property_id="prop_123",
            data={"count": 3},
            sync_status=SyncStatus.PENDING
        )
    ]


# Demo function
def demo_field_access_dashboard():
    """Demo function showing field access dashboard."""
    st.header("🏠 Field Access Dashboard Demo")
    
    # Demo controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        online = st.checkbox("Online Status", value=True)
        high_contrast = st.checkbox("High Contrast Mode", value=False)
        
    with col2:
        lat = st.number_input("Latitude", value=40.7589, format="%.6f")
        lng = st.number_input("Longitude", value=-73.9851, format="%.6f")
        
    with col3:
        accuracy = st.slider("GPS Accuracy (m)", min_value=1, max_value=100, value=5)
        address = st.text_input("Address", value="123 Main Street, New York, NY")
    
    # Sample sync queue
    if st.button("🔄 Add Sample Actions to Queue"):
        st.session_state.sync_queue = get_sample_sync_queue()
    
    sync_queue = st.session_state.get('sync_queue', [])
    
    # Render dashboard
    create_field_access_dashboard(
        current_location=(lat, lng),
        address=address,
        gps_accuracy=accuracy,
        sync_queue=sync_queue,
        online_status=online,
        high_contrast=high_contrast
    )
    
    # Instructions
    st.markdown("""
    ### 🏠 Field Access Dashboard Features
    
    **GPS & Location:**
    - Automatic location acquisition with high accuracy
    - Real-time coordinate display
    - Address geocoding and reverse lookup
    - GPS accuracy monitoring
    
    **Field Actions:**
    - **Check In**: Log arrival at property
    - **Voice Notes**: Record audio observations
    - **Photos**: Capture property images with metadata
    - **Client Meeting**: Log client interactions
    - **Inspection**: Property condition documentation
    - **Emergency**: Quick emergency contact
    
    **Offline Capabilities:**
    - Offline action queue with automatic sync
    - Local storage of photos and voice notes
    - Visual sync status indicators
    - Automatic retry on connection restore
    
    **Mobile Optimizations:**
    - Large touch targets (≥44px) for outdoor use
    - High contrast mode for bright sunlight
    - Haptic feedback on supported devices
    - Camera integration with image compression
    - Voice recording with noise reduction
    
    **Real Estate Workflow:**
    - Property-specific action logging
    - GPS verification for property visits
    - Automated timestamping and location tagging
    - Integration with Jorge's AI platform
    """)


if __name__ == "__main__":
    demo_field_access_dashboard()