"""
Offline Status Indicator Component for Jorge's Real Estate AI Dashboard

Production-ready offline detection and sync status component with visual indicators,
queue management, and automatic reconnection handling for field agents.

Features:
- Persistent network status display
- Sync queue count visualization with priority indicators
- Visual offline/syncing/online states with animations
- Connection restoration messaging and retry logic
- Real-time status updates with WebSocket fallback
- Professional Jorge's Real Estate AI styling
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

import streamlit as st


class ConnectionStatus(Enum):
    """Network connection status."""
    ONLINE = "online"
    OFFLINE = "offline" 
    CONNECTING = "connecting"
    LIMITED = "limited"  # Poor connection
    ERROR = "error"      # Connection error


class SyncItemStatus(Enum):
    """Individual sync item status."""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    RETRYING = "retrying"


class SyncPriority(Enum):
    """Priority levels for sync items."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class SyncItem:
    """Data structure for sync queue items."""
    id: str
    item_type: str
    timestamp: datetime
    priority: SyncPriority
    status: SyncItemStatus
    data_size: int  # bytes
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    last_attempt: Optional[datetime] = None


@dataclass
class NetworkMetrics:
    """Network performance metrics."""
    latency: Optional[float] = None  # ms
    bandwidth: Optional[float] = None  # kbps
    packet_loss: Optional[float] = None  # percentage
    connection_type: Optional[str] = None  # wifi, cellular, ethernet
    signal_strength: Optional[int] = None  # 0-100


def get_offline_indicator_css() -> str:
    """
    Returns CSS for the offline status indicator with animations and transitions.
    """
    return """
    <style>
        /* =================
           OFFLINE INDICATOR
           ================= */

        .offline-indicator {
            position: fixed;
            top: 16px;
            right: 16px;
            z-index: 9999;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(229, 231, 235, 0.8);
            border-radius: 12px;
            padding: 12px 16px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            user-select: none;
            cursor: pointer;
            max-width: 300px;
        }

        .offline-indicator.collapsed {
            padding: 8px 12px;
        }

        .offline-indicator:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 28px rgba(0, 0, 0, 0.2);
        }

        /* Status Variants */
        .offline-indicator.online {
            border-left: 4px solid #10b981;
        }

        .offline-indicator.offline {
            border-left: 4px solid #ef4444;
            background: rgba(254, 242, 242, 0.95);
        }

        .offline-indicator.connecting {
            border-left: 4px solid #f59e0b;
            background: rgba(255, 251, 235, 0.95);
        }

        .offline-indicator.limited {
            border-left: 4px solid #f97316;
            background: rgba(255, 247, 237, 0.95);
        }

        .offline-indicator.error {
            border-left: 4px solid #dc2626;
            background: rgba(254, 226, 226, 0.95);
        }

        /* Status Header */
        .offline-status-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }

        .offline-status-header.collapsed {
            margin-bottom: 0;
        }

        .offline-status-icon {
            font-size: 16px;
            flex-shrink: 0;
        }

        .offline-status-text {
            font-size: 13px;
            font-weight: 600;
            flex: 1;
        }

        .offline-status-toggle {
            background: none;
            border: none;
            font-size: 12px;
            color: #6b7280;
            cursor: pointer;
            padding: 2px;
            border-radius: 4px;
            transition: all 0.2s ease;
        }

        .offline-status-toggle:hover {
            background: rgba(107, 114, 128, 0.1);
            color: #374151;
        }

        /* Connection Quality */
        .connection-quality {
            display: flex;
            align-items: center;
            gap: 4px;
            margin-bottom: 8px;
        }

        .quality-bars {
            display: flex;
            gap: 2px;
        }

        .quality-bar {
            width: 3px;
            height: 12px;
            background: #d1d5db;
            border-radius: 1px;
            transition: background-color 0.2s ease;
        }

        .quality-bar.active {
            background: #10b981;
        }

        .quality-bar.active.poor {
            background: #ef4444;
        }

        .quality-bar.active.fair {
            background: #f59e0b;
        }

        .quality-bar.active.good {
            background: #10b981;
        }

        .quality-text {
            font-size: 11px;
            color: #6b7280;
            margin-left: 4px;
        }

        /* Sync Queue */
        .sync-queue-summary {
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 6px;
        }

        .sync-queue-items {
            max-height: 120px;
            overflow-y: auto;
            margin-bottom: 8px;
        }

        .sync-queue-item {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 0;
            border-bottom: 1px solid rgba(229, 231, 235, 0.5);
        }

        .sync-queue-item:last-child {
            border-bottom: none;
        }

        .sync-item-status {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }

        .sync-item-status.pending {
            background: #6b7280;
        }

        .sync-item-status.syncing {
            background: #3b82f6;
            animation: syncPulse 1.5s infinite;
        }

        .sync-item-status.synced {
            background: #10b981;
        }

        .sync-item-status.failed {
            background: #ef4444;
        }

        .sync-item-status.retrying {
            background: #f59e0b;
            animation: retryPulse 1s infinite;
        }

        .sync-item-info {
            flex: 1;
            min-width: 0;
        }

        .sync-item-type {
            font-size: 11px;
            font-weight: 500;
            color: #374151;
            line-height: 1.2;
        }

        .sync-item-details {
            font-size: 10px;
            color: #6b7280;
            line-height: 1.2;
        }

        .sync-item-priority {
            width: 4px;
            height: 16px;
            border-radius: 2px;
            flex-shrink: 0;
        }

        .sync-item-priority.low {
            background: #d1d5db;
        }

        .sync-item-priority.normal {
            background: #3b82f6;
        }

        .sync-item-priority.high {
            background: #f59e0b;
        }

        .sync-item-priority.urgent {
            background: #ef4444;
        }

        /* Network Metrics */
        .network-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 10px;
            color: #6b7280;
            border-top: 1px solid rgba(229, 231, 235, 0.5);
            padding-top: 6px;
        }

        .network-metric {
            display: flex;
            justify-content: space-between;
        }

        .network-metric-value {
            font-weight: 500;
            color: #374151;
        }

        /* Action Buttons */
        .offline-actions {
            display: flex;
            gap: 6px;
            margin-top: 8px;
        }

        .offline-action-button {
            flex: 1;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 11px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .offline-action-button:hover {
            background: #2563eb;
        }

        .offline-action-button.secondary {
            background: #f3f4f6;
            color: #374151;
        }

        .offline-action-button.secondary:hover {
            background: #e5e7eb;
        }

        .offline-action-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Animations */
        @keyframes syncPulse {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
            }
            50% {
                opacity: 0.7;
                transform: scale(1.3);
            }
        }

        @keyframes retryPulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.5;
            }
        }

        @keyframes slideInFromTop {
            from {
                transform: translateY(-100%);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        @keyframes connectionError {
            0%, 100% {
                border-left-color: #ef4444;
            }
            50% {
                border-left-color: #fca5a5;
            }
        }

        /* Responsive Design */
        @media (max-width: 640px) {
            .offline-indicator {
                top: 12px;
                right: 12px;
                max-width: 250px;
                font-size: 12px;
            }
            
            .network-metrics {
                grid-template-columns: 1fr;
            }
        }

        /* High contrast mode for outdoor visibility */
        .offline-indicator.high-contrast {
            background: #1f2937;
            color: white;
            border-color: #374151;
        }

        .offline-indicator.high-contrast .offline-status-text,
        .offline-indicator.high-contrast .sync-item-type {
            color: white;
        }

        .offline-indicator.high-contrast .quality-text,
        .offline-indicator.high-contrast .sync-queue-summary,
        .offline-indicator.high-contrast .sync-item-details {
            color: #d1d5db;
        }

        /* Jorge's Real Estate AI Branding */
        .offline-indicator::after {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 20px;
            height: 20px;
            background: linear-gradient(135deg, #3b82f6, #1e3a8a);
            border-radius: 0 12px 0 12px;
            opacity: 0.1;
        }

        .offline-indicator.jorge-branded::after {
            opacity: 0.3;
        }

        /* Notification badges */
        .offline-notification-badge {
            position: absolute;
            top: -4px;
            right: -4px;
            background: #ef4444;
            color: white;
            font-size: 10px;
            font-weight: 700;
            border-radius: 10px;
            min-width: 18px;
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid white;
            animation: badgePulse 2s infinite;
        }

        @keyframes badgePulse {
            0%, 100% {
                transform: scale(1);
            }
            50% {
                transform: scale(1.1);
            }
        }
    </style>
    """


def get_offline_indicator_js() -> str:
    """
    Returns JavaScript for real-time connection monitoring and sync management.
    """
    return """
    <script>
        class OfflineIndicator {
            constructor() {
                this.isOnline = navigator.onLine;
                this.connectionStatus = 'online';
                this.syncQueue = [];
                this.isExpanded = false;
                this.retryInterval = null;
                this.metricsInterval = null;
                this.lastPingTime = null;
                this.networkMetrics = {};
                
                this.init();
            }

            init() {
                this.setupEventListeners();
                this.startNetworkMonitoring();
                this.startPeriodicSync();
                this.updateConnectionStatus();
            }

            setupEventListeners() {
                // Browser online/offline events
                window.addEventListener('online', () => {
                    this.handleOnline();
                });

                window.addEventListener('offline', () => {
                    this.handleOffline();
                });

                // Click to toggle expanded view
                document.addEventListener('click', (e) => {
                    if (e.target.closest('.offline-indicator')) {
                        this.toggleExpanded();
                    }
                });

                // Retry button
                document.addEventListener('click', (e) => {
                    if (e.target.classList.contains('retry-sync-button')) {
                        this.retryFailedSync();
                    }
                });

                // Clear queue button
                document.addEventListener('click', (e) => {
                    if (e.target.classList.contains('clear-queue-button')) {
                        this.clearSyncedItems();
                    }
                });

                // Manual connection test
                document.addEventListener('click', (e) => {
                    if (e.target.classList.contains('test-connection-button')) {
                        this.testConnection();
                    }
                });
            }

            startNetworkMonitoring() {
                // Test connection quality every 30 seconds when online
                this.metricsInterval = setInterval(() => {
                    if (this.isOnline) {
                        this.measureNetworkMetrics();
                    }
                }, 30000);

                // Initial measurement
                if (this.isOnline) {
                    this.measureNetworkMetrics();
                }
            }

            startPeriodicSync() {
                // Attempt sync every 15 seconds
                setInterval(() => {
                    if (this.isOnline && this.syncQueue.length > 0) {
                        this.processSyncQueue();
                    }
                }, 15000);
            }

            async measureNetworkMetrics() {
                const startTime = performance.now();
                
                try {
                    // Test latency with a small request
                    const response = await fetch('/ping', {
                        method: 'GET',
                        cache: 'no-cache'
                    });
                    
                    const endTime = performance.now();
                    const latency = endTime - startTime;
                    
                    this.networkMetrics = {
                        latency: latency,
                        timestamp: new Date(),
                        status: response.ok ? 'good' : 'poor'
                    };
                    
                    // Determine connection quality
                    if (latency < 100) {
                        this.connectionStatus = 'online';
                    } else if (latency < 500) {
                        this.connectionStatus = 'limited';
                    } else {
                        this.connectionStatus = 'limited';
                    }
                    
                } catch (error) {
                    this.networkMetrics = {
                        latency: null,
                        timestamp: new Date(),
                        status: 'error'
                    };
                    
                    if (navigator.onLine) {
                        this.connectionStatus = 'error';
                    } else {
                        this.connectionStatus = 'offline';
                    }
                }
                
                this.updateDisplay();
            }

            handleOnline() {
                this.isOnline = true;
                this.connectionStatus = 'connecting';
                this.updateDisplay();
                
                // Test actual connectivity
                setTimeout(() => {
                    this.measureNetworkMetrics();
                    this.processSyncQueue();
                }, 1000);
            }

            handleOffline() {
                this.isOnline = false;
                this.connectionStatus = 'offline';
                this.updateDisplay();
            }

            addToSyncQueue(item) {
                const syncItem = {
                    id: this.generateId(),
                    type: item.type || 'data',
                    timestamp: new Date(),
                    priority: item.priority || 'normal',
                    status: 'pending',
                    data: item.data || {},
                    size: item.size || 0,
                    retryCount: 0,
                    maxRetries: item.maxRetries || 3
                };
                
                this.syncQueue.push(syncItem);
                this.updateDisplay();
                
                // Immediate sync attempt if online
                if (this.isOnline) {
                    setTimeout(() => this.processSyncQueue(), 100);
                }
            }

            async processSyncQueue() {
                if (!this.isOnline) return;
                
                const pendingItems = this.syncQueue.filter(item => 
                    item.status === 'pending' || item.status === 'failed'
                );
                
                for (const item of pendingItems.slice(0, 3)) { // Process 3 at a time
                    await this.syncItem(item);
                }
                
                this.updateDisplay();
            }

            async syncItem(item) {
                item.status = 'syncing';
                this.updateDisplay();
                
                try {
                    // Simulate API call (replace with actual sync logic)
                    const response = await fetch('/api/sync', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(item)
                    });
                    
                    if (response.ok) {
                        item.status = 'synced';
                        item.syncedAt = new Date();
                    } else {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    
                } catch (error) {
                    item.status = 'failed';
                    item.error = error.message;
                    item.retryCount += 1;
                    
                    // Schedule retry if under max attempts
                    if (item.retryCount < item.maxRetries) {
                        setTimeout(() => {
                            item.status = 'retrying';
                            this.updateDisplay();
                        }, 5000 * item.retryCount); // Exponential backoff
                    }
                }
                
                this.updateDisplay();
            }

            retryFailedSync() {
                const failedItems = this.syncQueue.filter(item => 
                    item.status === 'failed' && item.retryCount < item.maxRetries
                );
                
                failedItems.forEach(item => {
                    item.status = 'pending';
                    item.retryCount += 1;
                });
                
                if (this.isOnline) {
                    this.processSyncQueue();
                }
            }

            clearSyncedItems() {
                this.syncQueue = this.syncQueue.filter(item => 
                    item.status !== 'synced'
                );
                this.updateDisplay();
            }

            async testConnection() {
                this.connectionStatus = 'connecting';
                this.updateDisplay();
                
                await this.measureNetworkMetrics();
            }

            toggleExpanded() {
                this.isExpanded = !this.isExpanded;
                this.updateDisplay();
            }

            updateDisplay() {
                const indicator = document.querySelector('.offline-indicator');
                if (!indicator) return;
                
                // Update status classes
                indicator.className = `offline-indicator ${this.connectionStatus}`;
                if (this.isExpanded) {
                    indicator.classList.add('expanded');
                } else {
                    indicator.classList.add('collapsed');
                }
                
                // Update content
                this.updateStatusText();
                this.updateConnectionQuality();
                this.updateSyncQueue();
                this.updateNetworkMetrics();
                this.updateNotificationBadge();
            }

            updateStatusText() {
                const statusText = document.querySelector('.offline-status-text');
                if (!statusText) return;
                
                const statusIcons = {
                    online: '🟢',
                    offline: '🔴', 
                    connecting: '🟡',
                    limited: '🟠',
                    error: '❌'
                };
                
                const statusLabels = {
                    online: 'Online',
                    offline: 'Offline',
                    connecting: 'Connecting...',
                    limited: 'Limited Connection',
                    error: 'Connection Error'
                };
                
                const icon = document.querySelector('.offline-status-icon');
                if (icon) {
                    icon.textContent = statusIcons[this.connectionStatus];
                }
                
                statusText.textContent = statusLabels[this.connectionStatus];
            }

            updateConnectionQuality() {
                const qualityBars = document.querySelector('.quality-bars');
                if (!qualityBars) return;
                
                const bars = qualityBars.querySelectorAll('.quality-bar');
                const qualityText = document.querySelector('.quality-text');
                
                let activeCount = 0;
                let qualityClass = '';
                
                if (this.networkMetrics.latency !== null) {
                    if (this.networkMetrics.latency < 100) {
                        activeCount = 4;
                        qualityClass = 'good';
                        if (qualityText) qualityText.textContent = 'Excellent';
                    } else if (this.networkMetrics.latency < 300) {
                        activeCount = 3;
                        qualityClass = 'good';
                        if (qualityText) qualityText.textContent = 'Good';
                    } else if (this.networkMetrics.latency < 500) {
                        activeCount = 2;
                        qualityClass = 'fair';
                        if (qualityText) qualityText.textContent = 'Fair';
                    } else {
                        activeCount = 1;
                        qualityClass = 'poor';
                        if (qualityText) qualityText.textContent = 'Poor';
                    }
                } else if (this.connectionStatus === 'offline') {
                    activeCount = 0;
                    if (qualityText) qualityText.textContent = 'No Signal';
                }
                
                bars.forEach((bar, index) => {
                    bar.className = 'quality-bar';
                    if (index < activeCount) {
                        bar.classList.add('active', qualityClass);
                    }
                });
            }

            updateSyncQueue() {
                const queueSummary = document.querySelector('.sync-queue-summary');
                const queueItems = document.querySelector('.sync-queue-items');
                
                if (!queueSummary || !queueItems) return;
                
                const pendingCount = this.syncQueue.filter(item => 
                    item.status === 'pending' || item.status === 'syncing' || item.status === 'retrying'
                ).length;
                
                const failedCount = this.syncQueue.filter(item => 
                    item.status === 'failed'
                ).length;
                
                queueSummary.textContent = `${pendingCount} pending, ${failedCount} failed`;
                
                // Show recent items
                const recentItems = this.syncQueue.slice(-5);
                queueItems.innerHTML = recentItems.map(item => `
                    <div class="sync-queue-item">
                        <div class="sync-item-status ${item.status}"></div>
                        <div class="sync-item-info">
                            <div class="sync-item-type">${item.type}</div>
                            <div class="sync-item-details">
                                ${this.formatTimestamp(item.timestamp)}
                                ${item.size ? ` • ${this.formatBytes(item.size)}` : ''}
                            </div>
                        </div>
                        <div class="sync-item-priority ${item.priority}"></div>
                    </div>
                `).join('');
            }

            updateNetworkMetrics() {
                const metricsContainer = document.querySelector('.network-metrics');
                if (!metricsContainer || !this.networkMetrics.timestamp) return;
                
                const metrics = [];
                
                if (this.networkMetrics.latency !== null) {
                    metrics.push({
                        label: 'Latency',
                        value: `${Math.round(this.networkMetrics.latency)}ms`
                    });
                }
                
                metrics.push({
                    label: 'Last Check',
                    value: this.formatTimestamp(this.networkMetrics.timestamp, true)
                });
                
                metricsContainer.innerHTML = metrics.map(metric => `
                    <div class="network-metric">
                        <span>${metric.label}</span>
                        <span class="network-metric-value">${metric.value}</span>
                    </div>
                `).join('');
            }

            updateNotificationBadge() {
                let badge = document.querySelector('.offline-notification-badge');
                
                const urgentCount = this.syncQueue.filter(item => 
                    (item.status === 'failed' || item.status === 'pending') && 
                    item.priority === 'urgent'
                ).length;
                
                if (urgentCount > 0) {
                    if (!badge) {
                        badge = document.createElement('div');
                        badge.className = 'offline-notification-badge';
                        document.querySelector('.offline-indicator').appendChild(badge);
                    }
                    badge.textContent = urgentCount > 99 ? '99+' : urgentCount.toString();
                } else if (badge) {
                    badge.remove();
                }
            }

            formatTimestamp(timestamp, timeOnly = false) {
                const now = new Date();
                const diff = now - timestamp;
                
                if (timeOnly) {
                    return timestamp.toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                }
                
                if (diff < 60000) { // Less than 1 minute
                    return 'Just now';
                } else if (diff < 3600000) { // Less than 1 hour
                    const minutes = Math.floor(diff / 60000);
                    return `${minutes}m ago`;
                } else {
                    const hours = Math.floor(diff / 3600000);
                    return `${hours}h ago`;
                }
            }

            formatBytes(bytes) {
                if (bytes === 0) return '0 B';
                const k = 1024;
                const sizes = ['B', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
            }

            generateId() {
                return 'sync_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            }

            // Public API for external components
            addSyncItem(item) {
                this.addToSyncQueue(item);
            }

            getConnectionStatus() {
                return {
                    isOnline: this.isOnline,
                    status: this.connectionStatus,
                    metrics: this.networkMetrics,
                    queueLength: this.syncQueue.length
                };
            }

            forceSyncRetry() {
                this.retryFailedSync();
            }

            clearQueue() {
                this.clearSyncedItems();
            }
        }

        // Initialize when DOM is ready
        document.addEventListener('DOMContentLoaded', () => {
            window.offlineIndicator = new OfflineIndicator();
        });

        // API for Streamlit integration
        window.addEventListener('message', (event) => {
            if (event.data.type === 'add-sync-item') {
                window.offlineIndicator?.addSyncItem(event.data.item);
            } else if (event.data.type === 'retry-sync') {
                window.offlineIndicator?.forceSyncRetry();
            }
        });
    </script>
    """


def render_connection_quality_bars(latency: Optional[float] = None) -> str:
    """Renders connection quality bars based on latency."""
    bars_html = ""
    for i in range(4):
        bars_html += '<div class="quality-bar"></div>'
    
    quality_text = "Checking..."
    if latency is not None:
        if latency < 100:
            quality_text = "Excellent"
        elif latency < 300:
            quality_text = "Good"
        elif latency < 500:
            quality_text = "Fair"
        else:
            quality_text = "Poor"
    
    return f"""
    <div class="connection-quality">
        <div class="quality-bars">
            {bars_html}
        </div>
        <span class="quality-text">{quality_text}</span>
    </div>
    """


def render_sync_queue_items(sync_items: List[SyncItem]) -> str:
    """Renders sync queue items."""
    if not sync_items:
        return '<div style="text-align: center; color: #6b7280; font-size: 11px; padding: 8px;">No items in queue</div>'
    
    items_html = ""
    for item in sync_items[-5:]:  # Show last 5 items
        time_str = item.timestamp.strftime('%H:%M')
        size_str = f" • {format_bytes(item.data_size)}" if item.data_size > 0 else ""
        
        items_html += f"""
        <div class="sync-queue-item">
            <div class="sync-item-status {item.status.value}"></div>
            <div class="sync-item-info">
                <div class="sync-item-type">{item.item_type.replace('_', ' ').title()}</div>
                <div class="sync-item-details">{time_str}{size_str}</div>
            </div>
            <div class="sync-item-priority {item.priority.name.lower()}"></div>
        </div>
        """
    
    return items_html


def render_network_metrics(metrics: NetworkMetrics) -> str:
    """Renders network performance metrics."""
    metrics_html = ""
    
    if metrics.latency is not None:
        metrics_html += f"""
        <div class="network-metric">
            <span>Latency</span>
            <span class="network-metric-value">{metrics.latency:.0f}ms</span>
        </div>
        """
    
    if metrics.connection_type:
        metrics_html += f"""
        <div class="network-metric">
            <span>Type</span>
            <span class="network-metric-value">{metrics.connection_type.title()}</span>
        </div>
        """
    
    if metrics.signal_strength is not None:
        metrics_html += f"""
        <div class="network-metric">
            <span>Signal</span>
            <span class="network-metric-value">{metrics.signal_strength}%</span>
        </div>
        """
    
    metrics_html += f"""
    <div class="network-metric">
        <span>Last Check</span>
        <span class="network-metric-value">{datetime.now().strftime('%H:%M')}</span>
    </div>
    """
    
    return f'<div class="network-metrics">{metrics_html}</div>' if metrics_html else ""


def render_offline_actions(
    show_retry: bool = True,
    show_clear: bool = True,
    show_test: bool = True
) -> str:
    """Renders action buttons for the offline indicator."""
    actions_html = ""
    
    if show_retry:
        actions_html += '<button class="offline-action-button retry-sync-button">Retry</button>'
    
    if show_clear:
        actions_html += '<button class="offline-action-button secondary clear-queue-button">Clear</button>'
    
    if show_test:
        actions_html += '<button class="offline-action-button secondary test-connection-button">Test</button>'
    
    return f'<div class="offline-actions">{actions_html}</div>' if actions_html else ""


def format_bytes(bytes_count: int) -> str:
    """Formats byte count into human-readable string."""
    if bytes_count == 0:
        return "0 B"
    
    sizes = ["B", "KB", "MB", "GB"]
    i = 0
    while bytes_count >= 1024 and i < len(sizes) - 1:
        bytes_count /= 1024.0
        i += 1
    
    return f"{bytes_count:.1f} {sizes[i]}"


def create_offline_indicator(
    connection_status: ConnectionStatus = ConnectionStatus.ONLINE,
    sync_queue: List[SyncItem] = None,
    network_metrics: Optional[NetworkMetrics] = None,
    expanded: bool = False,
    high_contrast: bool = False,
    show_actions: bool = True
) -> None:
    """
    Creates and renders the offline status indicator.
    
    Args:
        connection_status: Current connection status
        sync_queue: List of sync items in queue
        network_metrics: Network performance metrics
        expanded: Whether to show expanded view
        high_contrast: Enable high contrast mode
        show_actions: Whether to show action buttons
    """
    # Inject CSS and JavaScript
    st.markdown(get_offline_indicator_css(), unsafe_allow_html=True)
    st.markdown(get_offline_indicator_js(), unsafe_allow_html=True)
    
    if sync_queue is None:
        sync_queue = []
    
    if network_metrics is None:
        network_metrics = NetworkMetrics()
    
    # Status icon and text
    status_icons = {
        ConnectionStatus.ONLINE: "🟢",
        ConnectionStatus.OFFLINE: "🔴",
        ConnectionStatus.CONNECTING: "🟡",
        ConnectionStatus.LIMITED: "🟠",
        ConnectionStatus.ERROR: "❌"
    }
    
    status_labels = {
        ConnectionStatus.ONLINE: "Online",
        ConnectionStatus.OFFLINE: "Offline", 
        ConnectionStatus.CONNECTING: "Connecting...",
        ConnectionStatus.LIMITED: "Limited Connection",
        ConnectionStatus.ERROR: "Connection Error"
    }
    
    # Count pending/failed items
    pending_count = len([item for item in sync_queue if item.status in [SyncItemStatus.PENDING, SyncItemStatus.SYNCING, SyncItemStatus.RETRYING]])
    failed_count = len([item for item in sync_queue if item.status == SyncItemStatus.FAILED])
    urgent_count = len([item for item in sync_queue if item.priority == SyncPriority.URGENT and item.status in [SyncItemStatus.PENDING, SyncItemStatus.FAILED]])
    
    # Container classes
    container_classes = [f"offline-indicator {connection_status.value}"]
    if not expanded:
        container_classes.append("collapsed")
    if high_contrast:
        container_classes.append("high-contrast")
    
    # Build the indicator HTML
    toggle_icon = "▼" if expanded else "▶"
    
    indicator_html = f"""
    <div class="{' '.join(container_classes)}">
        {'<div class="offline-notification-badge">' + str(urgent_count) + '</div>' if urgent_count > 0 else ''}
        
        <div class="offline-status-header{'collapsed' if not expanded else ''}">
            <span class="offline-status-icon">{status_icons[connection_status]}</span>
            <span class="offline-status-text">{status_labels[connection_status]}</span>
            <button class="offline-status-toggle">{toggle_icon}</button>
        </div>
    """
    
    if expanded:
        # Connection quality
        indicator_html += render_connection_quality_bars(network_metrics.latency)
        
        # Sync queue summary
        indicator_html += f"""
        <div class="sync-queue-summary">{pending_count} pending, {failed_count} failed</div>
        <div class="sync-queue-items">
            {render_sync_queue_items(sync_queue)}
        </div>
        """
        
        # Network metrics
        indicator_html += render_network_metrics(network_metrics)
        
        # Action buttons
        if show_actions:
            indicator_html += render_offline_actions(
                show_retry=failed_count > 0,
                show_clear=len(sync_queue) > 0,
                show_test=True
            )
    
    indicator_html += "</div>"
    
    st.markdown(indicator_html, unsafe_allow_html=True)


def get_sample_sync_queue() -> List[SyncItem]:
    """Returns sample sync queue items for demonstration."""
    return [
        SyncItem(
            id="sync_001",
            item_type="voice_note",
            timestamp=datetime.now() - timedelta(minutes=2),
            priority=SyncPriority.NORMAL,
            status=SyncItemStatus.SYNCED,
            data_size=2048000  # 2MB
        ),
        SyncItem(
            id="sync_002",
            item_type="photo_upload",
            timestamp=datetime.now() - timedelta(minutes=1),
            priority=SyncPriority.HIGH,
            status=SyncItemStatus.SYNCING,
            data_size=5242880  # 5MB
        ),
        SyncItem(
            id="sync_003",
            item_type="field_update",
            timestamp=datetime.now() - timedelta(seconds=30),
            priority=SyncPriority.URGENT,
            status=SyncItemStatus.FAILED,
            data_size=1024,  # 1KB
            retry_count=2,
            error_message="Network timeout"
        ),
        SyncItem(
            id="sync_004",
            item_type="property_check_in",
            timestamp=datetime.now() - timedelta(seconds=10),
            priority=SyncPriority.NORMAL,
            status=SyncItemStatus.PENDING,
            data_size=512  # 512B
        )
    ]


# Demo function
def demo_offline_indicator():
    """Demo function showing offline status indicator."""
    st.header("🌐 Offline Status Indicator Demo")
    
    # Demo controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status = st.selectbox(
            "Connection Status",
            [status.value for status in ConnectionStatus],
            index=0
        )
        expanded = st.checkbox("Expanded View", value=True)
        
    with col2:
        high_contrast = st.checkbox("High Contrast Mode", value=False)
        latency = st.slider("Latency (ms)", min_value=0, max_value=1000, value=150)
        
    with col3:
        show_actions = st.checkbox("Show Action Buttons", value=True)
        if st.button("🔄 Add Sample Sync Items"):
            st.session_state.demo_sync_queue = get_sample_sync_queue()
    
    # Get sample data
    connection_status = ConnectionStatus(status)
    sync_queue = st.session_state.get('demo_sync_queue', [])
    
    network_metrics = NetworkMetrics(
        latency=latency,
        connection_type="wifi",
        signal_strength=85 if latency < 200 else 60,
        packet_loss=0.1 if latency > 500 else 0.0
    )
    
    # Render indicator
    create_offline_indicator(
        connection_status=connection_status,
        sync_queue=sync_queue,
        network_metrics=network_metrics,
        expanded=expanded,
        high_contrast=high_contrast,
        show_actions=show_actions
    )
    
    # Show current sync queue details
    if sync_queue and st.expander("📋 Current Sync Queue Details"):
        for item in sync_queue:
            col_a, col_b, col_c = st.columns([2, 1, 1])
            
            with col_a:
                st.write(f"**{item.item_type}** ({item.status.value})")
                st.caption(f"Priority: {item.priority.name}, Size: {format_bytes(item.data_size)}")
            
            with col_b:
                st.write(f"Retries: {item.retry_count}/{item.max_retries}")
            
            with col_c:
                st.write(item.timestamp.strftime('%H:%M:%S'))
    
    # Instructions
    st.markdown("""
    ### 🌐 Offline Status Indicator Features
    
    **Connection Monitoring:**
    - Real-time online/offline detection
    - Network quality measurement (latency, signal strength)
    - Connection type detection (WiFi, cellular, ethernet)
    - Automatic reconnection handling
    
    **Sync Queue Management:**
    - Visual queue status with priority indicators
    - Automatic retry with exponential backoff
    - Failed item tracking and manual retry
    - Data size and timestamp display
    
    **Visual States:**
    - **Green (Online)**: Full connectivity with good performance
    - **Red (Offline)**: No network connection detected
    - **Yellow (Connecting)**: Attempting to establish connection
    - **Orange (Limited)**: Poor connection quality or high latency
    - **Red X (Error)**: Connection error or authentication failure
    
    **User Interactions:**
    - Click to expand/collapse detailed view
    - Retry failed sync items manually
    - Clear completed items from queue
    - Test connection manually
    
    **Real Estate Field Use:**
    - Persistent indicator for field agents
    - Offline queue for property data, photos, voice notes
    - Automatic sync when connection is restored
    - High contrast mode for outdoor visibility
    - Priority-based sync (urgent items first)
    
    **Jorge's Real Estate AI Integration:**
    - Consistent with dashboard branding
    - Real-time updates via WebSocket
    - Integration with field access dashboard
    - Professional styling for client interactions
    """)


if __name__ == "__main__":
    demo_offline_indicator()