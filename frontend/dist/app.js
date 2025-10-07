/**
 * Not Pinnacle Odds Tracker - Frontend Application
 * Real-time odds tracking with WebSocket connections
 */

class PinnacleOddsApp {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.autoRefreshInterval = null;
        this.countdownInterval = null;
        this.priceChart = null;
        this.currentTab = 'odds';
        this.currentView = 'grid';
        this.settings = {
            changeThreshold: 5,
            autoRefresh: 30,
            notificationsEnabled: true,
            soundEnabled: true,
            oddsFormat: 'american',
            timezone: 'UTC'
        };
        
        this.init();
    }

    async init() {
        this.setupEventListeners();
        this.loadSettings();
        this.connectWebSocket();
        await this.loadInitialData();
        this.startAutoRefresh();
        this.startCountdownTimer();
        this.setupNotifications();
    }

    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.currentTarget.dataset.tab;
                this.switchTab(tabName);
            });
        });

        // View toggle
        document.querySelectorAll('.view-toggle').forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                const view = e.currentTarget.dataset.view;
                this.switchView(view);
            });
        });


        // Filters
        document.getElementById('sport-filter').addEventListener('change', () => {
            this.loadOdds();
        });

        document.getElementById('market-filter').addEventListener('change', () => {
            this.loadOdds();
        });

        document.getElementById('drops-time-filter').addEventListener('change', () => {
            this.loadDrops();
        });

        // Settings
        document.getElementById('change-threshold').addEventListener('change', (e) => {
            this.settings.changeThreshold = parseFloat(e.target.value);
            this.saveSettings();
        });

        document.getElementById('auto-refresh').addEventListener('change', (e) => {
            this.settings.autoRefresh = parseInt(e.target.value);
            this.saveSettings();
            this.startAutoRefresh();
        });

        document.getElementById('notifications-enabled').addEventListener('change', (e) => {
            this.settings.notificationsEnabled = e.target.checked;
            this.saveSettings();
        });

        document.getElementById('sound-enabled').addEventListener('change', (e) => {
            this.settings.soundEnabled = e.target.checked;
            this.saveSettings();
        });

        document.getElementById('odds-format').addEventListener('change', (e) => {
            this.settings.oddsFormat = e.target.value;
            this.saveSettings();
            this.loadOdds();
        });

        document.getElementById('timezone').addEventListener('change', (e) => {
            this.settings.timezone = e.target.value;
            this.saveSettings();
        });

        // Settings buttons
        document.getElementById('save-settings').addEventListener('click', () => {
            this.saveSettings();
            this.showToast('Settings saved successfully!', 'success');
        });

        document.getElementById('reset-settings').addEventListener('click', () => {
            this.resetSettings();
            this.showToast('Settings reset to defaults!', 'info');
        });

        // Price history pane
        document.getElementById('close-pane').addEventListener('click', () => {
            this.closePriceHistoryPane();
        });

        // Search
        document.getElementById('history-event-search').addEventListener('input', (e) => {
            this.filterHistory(e.target.value);
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus('connected');
            this.reconnectAttempts = 0;
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus('disconnected');
            this.attemptReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('error');
        };
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            this.updateConnectionStatus('reconnecting');
            
            setTimeout(() => {
                console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                this.connectWebSocket();
            }, this.reconnectDelay * this.reconnectAttempts);
        } else {
            this.updateConnectionStatus('failed');
        }
    }

    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        const icon = statusElement.querySelector('i');
        const text = statusElement.querySelector('span');
        
        statusElement.className = `status-indicator ${status}`;
        
        switch (status) {
            case 'connected':
                text.textContent = 'Connected';
                break;
            case 'disconnected':
                text.textContent = 'Disconnected';
                break;
            case 'reconnecting':
                text.textContent = 'Reconnecting...';
                break;
            case 'failed':
                text.textContent = 'Connection Failed';
                break;
            default:
                text.textContent = 'Connecting...';
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'odds_change':
                this.handleOddsChange(data.data);
                break;
            case 'odds_update':
                this.handleOddsUpdate(data.data);
                break;
            default:
                console.log('Unknown WebSocket message type:', data.type);
        }
    }

    handleOddsChange(changeData) {
        // Update drops tab badge
        const badge = document.getElementById('drops-badge');
        const currentCount = parseInt(badge.textContent) || 0;
        badge.textContent = currentCount + 1;

        // Show notification
        if (this.settings.notificationsEnabled) {
            this.showNotification(
                'Odds Change Detected',
                `${changeData.sport} - ${changeData.game}`,
                'warning'
            );
        }

        // Play sound
        if (this.settings.soundEnabled) {
            this.playNotificationSound();
        }

        // If on drops tab, refresh the data
        if (this.currentTab === 'drops') {
            this.loadDrops();
        }
    }

    handleOddsUpdate(oddsData) {
        // If on odds tab, refresh the data
        if (this.currentTab === 'odds') {
            this.loadOdds();
        }
    }

    async loadInitialData() {
        this.showLoading(true);
        
        try {
            await Promise.all([
                this.loadSports(),
                this.loadMarkets(),
                this.loadOdds(),
                this.loadStats()
            ]);
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showToast('Error loading data', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async loadSports() {
        try {
            const response = await fetch('/api/sports');
            const data = await response.json();
            
            const select = document.getElementById('sport-filter');
            select.innerHTML = '<option value="">All Sports</option>';
            
            data.sports.forEach(sport => {
                const option = document.createElement('option');
                option.value = sport.sport_key;
                option.textContent = sport.sport_title;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading sports:', error);
        }
    }

    async loadMarkets() {
        try {
            const response = await fetch('/api/markets');
            const data = await response.json();
            
            const select = document.getElementById('market-filter');
            select.innerHTML = '<option value="">All Markets</option>';
            
            data.markets.forEach(market => {
                const option = document.createElement('option');
                option.value = market.market_key;
                option.textContent = market.market_name;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading markets:', error);
        }
    }

    async loadOdds() {
        try {
            const sportFilter = document.getElementById('sport-filter').value;
            const marketFilter = document.getElementById('market-filter').value;
            
            const params = new URLSearchParams();
            if (sportFilter) params.append('sport_key', sportFilter);
            if (marketFilter) params.append('market_key', marketFilter);
            
            const response = await fetch(`/api/odds?${params}`);
            const data = await response.json();
            
            this.renderOdds(data.odds);
        } catch (error) {
            console.error('Error loading odds:', error);
            this.showToast('Error loading odds', 'error');
        }
    }

    async loadDrops() {
        try {
            const timeFilter = document.getElementById('drops-time-filter').value;
            const minChange = this.settings.changeThreshold / 100;
            
            const response = await fetch(`/api/odds/changes?hours=${timeFilter}&min_change_percentage=${minChange}`);
            const data = await response.json();
            
            this.renderDrops(data.changes || []);
            
            // Update badge
            document.getElementById('drops-badge').textContent = data.count || 0;
        } catch (error) {
            console.error('Error loading drops:', error);
            this.showToast('Error loading drops', 'error');
            this.renderDrops([]);
        }
    }

    async loadHistory() {
        try {
            const response = await fetch('/api/odds/changes?hours=168'); // Last week
            const data = await response.json();
            
            this.renderHistory(data.changes || []);
        } catch (error) {
            console.error('Error loading history:', error);
            this.showToast('Error loading history', 'error');
            this.renderHistory([]);
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            
            document.getElementById('live-events').textContent = data.total_events;
            document.getElementById('changes-24h').textContent = data.recent_changes_24h;
            document.getElementById('flagged-count').textContent = data.flagged_changes;
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    renderOdds(odds) {
        const container = document.getElementById('odds-container');
        container.innerHTML = '';

        if (odds.length === 0) {
            container.innerHTML = `
                <div class="no-data">
                    <i class="fas fa-chart-line"></i>
                    <h3>No Odds Available</h3>
                    <p>No current odds data found. The scraper may still be running or there may be no active events.</p>
                </div>
            `;
            return;
        }

        // Group odds by sport, then by event
        const sportsData = this.groupOddsBySport(odds);

        Object.entries(sportsData).forEach(([sportTitle, events]) => {
            const sportSection = this.createSportSection(sportTitle, events);
            container.appendChild(sportSection);
        });
    }

    groupOddsBySport(odds) {
        const sports = {};
        
        odds.forEach(odd => {
            const sportTitle = odd.sport_title;
            if (!sports[sportTitle]) {
                sports[sportTitle] = {};
            }
            
            const eventKey = odd.event_id;
            if (!sports[sportTitle][eventKey]) {
                sports[sportTitle][eventKey] = {
                    event_id: odd.event_id,
                    home_team: odd.home_team,
                    away_team: odd.away_team,
                    commence_time: odd.commence_time,
                    sport_title: odd.sport_title,
                    odds: []
                };
            }
            sports[sportTitle][eventKey].odds.push(odd);
        });

        return sports;
    }

    groupOddsByEvent(odds) {
        const events = {};
        
        odds.forEach(odd => {
            const key = odd.event_id;
            if (!events[key]) {
                events[key] = {
                    event_id: odd.event_id,
                    home_team: odd.home_team,
                    away_team: odd.away_team,
                    commence_time: odd.commence_time,
                    sport_title: odd.sport_title,
                    odds: []
                };
            }
            events[key].odds.push(odd);
        });

        return Object.values(events);
    }

    createSportSection(sportTitle, events) {
        const section = document.createElement('div');
        section.className = 'sport-section';
        
        const eventCount = Object.keys(events).length;
        const sportIcon = this.getSportIcon(sportTitle);
        
        section.innerHTML = `
            <div class="sport-header">
                <div class="sport-title">
                    <div class="sport-icon">${sportIcon}</div>
                    ${sportTitle}
                </div>
                <div class="sport-count">${eventCount} event${eventCount !== 1 ? 's' : ''}</div>
            </div>
            <div class="events-list">
                ${Object.values(events).map(event => this.createEventCard(event)).join('')}
            </div>
        `;
        
        return section;
    }

    createEventCard(event) {
        const commenceTime = new Date(event.commence_time);
        const timeString = commenceTime.toLocaleString();
        const isLive = commenceTime <= new Date();
        
        const markets = this.groupOddsByMarket(event.odds);
        
        return `
            <div class="event-card ${isLive ? 'live' : ''}">
                <div class="event-header">
                    <div class="event-teams">
                        <div class="home-team">${event.home_team}</div>
                        <div class="away-team">@ ${event.away_team}</div>
                    </div>
                    <div class="event-time">${timeString}</div>
                </div>
                <div class="markets-row">
                    ${Object.entries(markets).map(([marketName, marketOdds]) => 
                        this.createMarketGroup(marketName, marketOdds)
                    ).join('')}
                </div>
            </div>
        `;
    }

    createMarketGroup(marketName, marketOdds) {
        return `
            <div class="market-group">
                <div class="market-title">${marketName}</div>
                <div class="market-options">
                    ${marketOdds.map(odd => this.createMarketOption(odd)).join('')}
                </div>
            </div>
        `;
    }

    createMarketOption(odd) {
        const oddsValue = this.formatOdds(odd.odds_value);
        const pointValue = odd.point_value ? ` (${odd.point_value})` : '';
        const isFavorite = Math.abs(odd.odds_value) < 120; // Consider odds under 120 as favorites
        
        return `
            <div class="market-option ${isFavorite ? 'favorite' : ''}">
                <div class="option-label">${odd.team_name}</div>
                <div class="option-odds">${oddsValue}</div>
                ${pointValue ? `<div class="option-point">${pointValue}</div>` : ''}
            </div>
        `;
    }

    groupOddsByMarket(odds) {
        const markets = {};
        odds.forEach(odd => {
            if (!markets[odd.market_name]) {
                markets[odd.market_name] = [];
            }
            markets[odd.market_name].push(odd);
        });
        return markets;
    }

    getSportIcon(sportTitle) {
        const icons = {
            'English Premier League': '⚽',
            'NFL': '🏈',
            'NBA': '🏀',
            'NHL': '🏒',
            'MLB': '⚾',
            'NCAA Football': '🏈',
            'NCAA Basketball': '🏀',
            'Champions League': '🏆',
            'Europa League': '🏆',
            'Conference League': '🏆'
        };
        return icons[sportTitle] || '⚽';
    }

    createOddsCard(event) {
        const card = document.createElement('div');
        card.className = 'odds-card';
        
        const commenceTime = new Date(event.commence_time);
        const timeString = commenceTime.toLocaleString();
        
        card.innerHTML = `
            <div class="odds-card-header">
                <div class="event-info">
                    <h3>${event.home_team} vs ${event.away_team}</h3>
                    <div class="event-meta">
                        <span class="sport-badge">${event.sport_title}</span>
                        <span class="time-info">${timeString}</span>
                    </div>
                </div>
            </div>
            <div class="odds-grid">
                ${this.renderOddsGrid(event.odds)}
            </div>
        `;
        
        return card;
    }

    renderOddsGrid(odds) {
        // Group odds by market
        const markets = {};
        odds.forEach(odd => {
            if (!markets[odd.market_name]) {
                markets[odd.market_name] = [];
            }
            markets[odd.market_name].push(odd);
        });

        let html = '';
        Object.entries(markets).forEach(([marketName, marketOdds]) => {
            html += `<div class="odds-market">
                <div class="odds-label">${marketName}</div>
                ${marketOdds.map(odd => this.renderOddsItem(odd)).join('')}
            </div>`;
        });

        return html;
    }

    renderOddsItem(odd) {
        const oddsValue = this.formatOdds(odd.odds_value);
        const pointValue = odd.point_value ? ` (${odd.point_value})` : '';
        
        return `
            <div class="odds-item">
                <div class="odds-label">${odd.team_name}</div>
                <div class="odds-value">${oddsValue}</div>
                ${pointValue ? `<div class="odds-point">${pointValue}</div>` : ''}
            </div>
        `;
    }

    renderDrops(changes) {
        const container = document.getElementById('drops-container');
        container.innerHTML = '';

        if (changes.length === 0) {
            container.innerHTML = '<div class="no-data">No significant odds drops detected</div>';
            return;
        }

        // Create table structure
        const table = document.createElement('table');
        table.className = 'drops-table';
        
        // Table header
        const thead = document.createElement('thead');
        thead.innerHTML = `
            <tr>
                <th>Match</th>
                <th>Starts</th>
                <th>Alert</th>
                <th>Outcome</th>
                <th>Price</th>
                <th>No Vig Price</th>
                <th>Drop Value</th>
            </tr>
        `;
        table.appendChild(thead);

        // Table body
        const tbody = document.createElement('tbody');
        
        changes.forEach(change => {
            const row = this.createDropTableRow(change);
            tbody.appendChild(row);
        });
        
        table.appendChild(tbody);
        container.appendChild(table);
    }

    createDropTableRow(change) {
        const row = document.createElement('tr');
        row.className = 'drop-row';
        
        // Format times
        const alertTime = new Date(change.detected_at);
        const alertTimeAgo = this.formatTimeAgo(alertTime);
        const startsIn = this.formatTimeUntilStart(change.commence_time);
        
        // Format price change with red new price
        const oldPrice = this.formatOdds(change.old_odds);
        const newPrice = this.formatOdds(change.new_odds);
        const priceChange = `${oldPrice} → <span class="new-price">${newPrice}</span>`;
        
        // Format outcome with point values for over/under and spreads
        let outcomeText = change.team_name;
        if (change.market_key === 'totals' && change.point_value) {
            const overUnder = change.team_name.toLowerCase().includes('over') ? 'Over' : 'Under';
            outcomeText = `${overUnder} ${change.point_value}`;
        } else if (change.market_key === 'spreads' && change.point_value) {
            const spreadSign = change.point_value > 0 ? '+' : '';
            outcomeText = `${change.team_name} ${spreadSign}${change.point_value}`;
        }
        
                // Calculate proper no-vig price
                let noVigPriceFormatted = '--';
                if (change.other_side_odds) {
                    if (change.market_key === 'h2h' && typeof change.other_side_odds === 'string' && change.other_side_odds.includes(',')) {
                        // Soccer three-way moneyline - parse comma-separated string and calculate no-vig using all three sides
                        const allOdds = change.other_side_odds.split(',').map(odds => parseFloat(odds));
                        const noVigPrice = this.calculateThreeWayNoVigPrice(change.new_odds, allOdds);
                        noVigPriceFormatted = this.formatOdds(noVigPrice);
                    } else if (typeof change.other_side_odds === 'string' && !change.other_side_odds.includes(',')) {
                        // Two-way market with string odds - convert to number
                        const otherOdds = parseFloat(change.other_side_odds);
                        const noVigPrice = this.calculateNoVigPrice(change.new_odds, otherOdds);
                        noVigPriceFormatted = this.formatOdds(noVigPrice);
                    } else if (typeof change.other_side_odds === 'number') {
                        // Two-way market with number odds
                        const noVigPrice = this.calculateNoVigPrice(change.new_odds, change.other_side_odds);
                        noVigPriceFormatted = this.formatOdds(noVigPrice);
                    }
                }
        
        // Format drop value
        const dropValue = change.change_percentage.toFixed(1) + '%';
        const dropClass = change.odds_change < 0 ? 'negative' : 'positive';
        
        row.innerHTML = `
            <td class="match-cell">
                <div class="match-info">
                    <div class="match-teams">${change.home_team} vs ${change.away_team}</div>
                    <div class="match-meta">
                        <span class="sport-badge">${change.sport_title}</span>
                        <span class="market-badge">${change.market_key === 'h2h' ? 'Moneyline (3-way)' : change.market_name}</span>
                    </div>
                </div>
            </td>
            <td class="starts-cell">${startsIn}</td>
            <td class="alert-cell">${alertTimeAgo}</td>
            <td class="outcome-cell">${outcomeText}</td>
            <td class="price-cell">${priceChange}</td>
            <td class="no-vig-cell">${noVigPriceFormatted}</td>
            <td class="drop-value-cell ${dropClass}">${dropValue}</td>
        `;
        
        // Add click handler for price history
        row.addEventListener('click', () => {
            this.showPriceHistory(change);
        });
        
        return row;
    }

    createDropItem(change) {
        const item = document.createElement('div');
        item.className = 'drop-item';
        
        const detectedTime = new Date(change.detected_at);
        const timeString = detectedTime.toLocaleString();
        
        const changeClass = change.odds_change < 0 ? 'negative' : 'positive';
        const changeIcon = change.odds_change < 0 ? 'fa-arrow-down' : 'fa-arrow-up';
        
        item.innerHTML = `
            <div class="drop-header">
                <div class="drop-event">
                    <h3>${change.home_team} vs ${change.away_team}</h3>
                    <div class="drop-meta">
                        <span class="sport-badge">${change.sport_title}</span>
                        <span class="drop-flag">${change.market_name}</span>
                    </div>
                </div>
                <div class="drop-time">${timeString}</div>
            </div>
            <div class="drop-details">
                <div class="drop-detail">
                    <div class="drop-detail-label">Team</div>
                    <div class="drop-detail-value">${change.team_name}</div>
                </div>
                <div class="drop-detail">
                    <div class="drop-detail-label">Old Odds</div>
                    <div class="drop-detail-value old">${this.formatOdds(change.old_odds)}</div>
                </div>
                <div class="drop-detail">
                    <div class="drop-detail-label">New Odds</div>
                    <div class="drop-detail-value new">${this.formatOdds(change.new_odds)}</div>
                </div>
                <div class="drop-detail">
                    <div class="drop-detail-label">Change</div>
                    <div class="drop-detail-value change ${changeClass}">
                        <i class="fas ${changeIcon}"></i>
                        ${change.change_percentage.toFixed(2)}%
                    </div>
                </div>
            </div>
        `;
        
        return item;
    }

    renderHistory(changes) {
        const container = document.getElementById('history-container');
        container.innerHTML = '';

        if (changes.length === 0) {
            container.innerHTML = '<div class="no-data">No history data available</div>';
            return;
        }

        changes.forEach(change => {
            const item = this.createHistoryItem(change);
            container.appendChild(item);
        });
    }

    createHistoryItem(change) {
        const item = document.createElement('div');
        item.className = 'history-item';
        
        const detectedTime = new Date(change.detected_at);
        const timeString = detectedTime.toLocaleString();
        
        item.innerHTML = `
            <div class="history-header">
                <h3>${change.home_team} vs ${change.away_team}</h3>
                <span class="time-info">${timeString}</span>
            </div>
            <div class="history-details">
                <div class="history-detail">
                    <strong>${change.sport_title}</strong> - ${change.market_name}
                </div>
                <div class="history-detail">
                    ${change.team_name}: ${this.formatOdds(change.old_odds)} → ${this.formatOdds(change.new_odds)}
                    <span class="change-percentage">(${change.change_percentage.toFixed(2)}%)</span>
                </div>
            </div>
        `;
        
        return item;
    }

    formatOdds(odds) {
        switch (this.settings.oddsFormat) {
            case 'decimal':
                return this.americanToDecimal(odds).toFixed(2);
            case 'fractional':
                return this.americanToFractional(odds);
            default:
                return odds > 0 ? `+${odds}` : odds.toString();
        }
    }

    americanToDecimal(american) {
        if (american > 0) {
            return (american / 100) + 1;
        } else {
            return (100 / Math.abs(american)) + 1;
        }
    }

    americanToFractional(american) {
        if (american > 0) {
            return `${american}/100`;
        } else {
            return `100/${Math.abs(american)}`;
        }
    }

    americanToDecimal(americanOdds) {
        if (americanOdds > 0) {
            return (americanOdds / 100) + 1;
        } else {
            return (100 / Math.abs(americanOdds)) + 1;
        }
    }

    calculateImpliedProbabilityDrop(oldOdds, newOdds) {
        // Convert American odds to decimal odds
        const oldDecimal = this.americanToDecimal(oldOdds);
        const newDecimal = this.americanToDecimal(newOdds);
        
        // Calculate implied probabilities
        const oldProbability = 1 / oldDecimal;
        const newProbability = 1 / newDecimal;
        
        // Calculate the difference in probabilities
        const probabilityDifference = newProbability - oldProbability;
        
        // Calculate percentage drop: (difference / initial probability) * 100
        if (oldProbability !== 0) {
            const percentageDrop = (probabilityDifference / oldProbability) * 100;
            return percentageDrop;
        } else {
            return 0;
        }
    }

    calculateNoVigPrice(odds1, odds2) {
        // Convert American odds to implied probabilities
        const prob1 = odds1 > 0 ? 100 / (odds1 + 100) : Math.abs(odds1) / (Math.abs(odds1) + 100);
        const prob2 = odds2 > 0 ? 100 / (odds2 + 100) : Math.abs(odds2) / (Math.abs(odds2) + 100);
        
        // Calculate total probability
        const totalProb = prob1 + prob2;
        
        // Calculate no-vig probabilities
        const noVigProb1 = prob1 / totalProb;
        const noVigProb2 = prob2 / totalProb;
        
        // Convert back to American odds
        const noVigOdds1 = noVigProb1 > 0.5 ? 
            -((noVigProb1 * 100) / (1 - noVigProb1)) : 
            ((1 - noVigProb1) * 100) / noVigProb1;
        
        return Math.round(noVigOdds1);
    }

    calculateThreeWayNoVigPrice(currentOdds, allOdds) {
        // For three-way moneyline, calculate no-vig using all three sides
        // Based on the example: Home +150, Draw +240, Away +180
        
        // Convert all odds to implied probabilities
        const probabilities = allOdds.map(odds => 
            odds > 0 ? 100 / (odds + 100) : Math.abs(odds) / (Math.abs(odds) + 100)
        );
        
        // Calculate total probability (including vig)
        const totalProb = probabilities.reduce((sum, prob) => sum + prob, 0);
        
        // Find the index of the current odds in the array
        const currentIndex = allOdds.findIndex(odds => Math.abs(odds - currentOdds) < 0.01);
        
        if (currentIndex === -1) {
            // Fallback to two-way calculation if current odds not found
            return this.calculateNoVigPrice(currentOdds, allOdds[0]);
        }
        
        // Remove vig by normalizing probabilities (divide each by total)
        const noVigProb = probabilities[currentIndex] / totalProb;
        
        // Convert back to American odds
        // Fair decimal odds = 1 / noVigProb
        // American odds = (1 / noVigProb - 1) * 100 (if > 1) or -100 / (1 / noVigProb - 1) (if < 1)
        const fairDecimal = 1 / noVigProb;
        
        let noVigOdds;
        if (fairDecimal >= 2) {
            // Positive American odds
            noVigOdds = (fairDecimal - 1) * 100;
        } else {
            // Negative American odds
            noVigOdds = -100 / (fairDecimal - 1);
        }
        
        return Math.round(noVigOdds);
    }

    formatTimeUntilStart(commenceTime) {
        const now = new Date();
        const start = new Date(commenceTime);
        const diffMs = start - now;
        
        if (diffMs < 0) {
            return 'Live';
        }
        
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        const diffHours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        
        if (diffDays > 0) {
            return `${diffDays}d ${diffHours}h`;
        } else if (diffHours > 0) {
            return `${diffHours}h ${diffMinutes}m`;
        } else {
            return `${diffMinutes}m`;
        }
    }

    formatTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        
        const diffMinutes = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffMinutes < 1) {
            return 'Just now';
        } else if (diffMinutes < 60) {
            return `${diffMinutes}m ago`;
        } else if (diffHours < 24) {
            return `${diffHours}h ago`;
        } else {
            return `${diffDays}d ago`;
        }
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');

        this.currentTab = tabName;

        // Load data for the new tab
        switch (tabName) {
            case 'odds':
                this.loadOdds();
                break;
            case 'drops':
                this.loadDrops();
                break;
            case 'history':
                this.loadHistory();
                break;
        }
    }

    switchView(view) {
        document.querySelectorAll('.view-toggle').forEach(toggle => {
            toggle.classList.remove('active');
        });
        document.querySelector(`[data-view="${view}"]`).classList.add('active');

        const container = document.getElementById('odds-container');
        container.className = `odds-container ${view}-view`;

        this.currentView = view;
    }

    startAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }

        if (this.settings.autoRefresh > 0) {
            this.autoRefreshInterval = setInterval(() => {
                switch (this.currentTab) {
                    case 'odds':
                        this.loadOdds();
                        break;
                    case 'drops':
                        this.loadDrops();
                        break;
                    case 'history':
                        this.loadHistory();
                        break;
                }
                this.loadStats();
            }, this.settings.autoRefresh * 1000);
        }
    }

    startCountdownTimer() {
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
        }

        // Update countdown every second
        this.countdownInterval = setInterval(() => {
            this.updateCountdownTimer();
        }, 1000);

        // Initial update
        this.updateCountdownTimer();
    }

    updateCountdownTimer() {
        const countdownElement = document.getElementById('next-scrape-countdown');
        const countdownContainer = document.querySelector('.countdown-timer');
        
        if (!countdownElement) return;

        // Get the last scrape time from the stats API to calculate next scrape
        this.getLastScrapeTime().then(lastScrapeTime => {
            if (!lastScrapeTime) {
                countdownElement.textContent = '--:--';
                return;
            }

            // Calculate next scrape time (5 minutes after last scrape)
            const lastScrape = new Date(lastScrapeTime);
            const nextScrape = new Date(lastScrape.getTime() + (5 * 60 * 1000)); // Add 5 minutes
            const now = new Date();

            // If next scrape time has passed, calculate the next 5-minute interval
            if (nextScrape <= now) {
                const minutesSinceLastScrape = Math.floor((now - lastScrape) / (5 * 60 * 1000));
                const nextScrapeTime = new Date(lastScrape.getTime() + ((minutesSinceLastScrape + 1) * 5 * 60 * 1000));
                
                const diff = nextScrapeTime - now;
                const minutesLeft = Math.max(0, Math.floor(diff / 60000));
                const secondsLeft = Math.max(0, Math.floor((diff % 60000) / 1000));

                const timeString = `${minutesLeft.toString().padStart(2, '0')}:${secondsLeft.toString().padStart(2, '0')}`;
                countdownElement.textContent = timeString;

                // Update styling based on time remaining
                countdownContainer.className = 'stat-item countdown-timer';
                if (minutesLeft === 0 && secondsLeft <= 30) {
                    countdownContainer.classList.add('critical');
                } else if (minutesLeft === 0 && secondsLeft <= 60) {
                    countdownContainer.classList.add('warning');
                }
            } else {
                // Next scrape is in the future
                const diff = nextScrape - now;
                const minutesLeft = Math.max(0, Math.floor(diff / 60000));
                const secondsLeft = Math.max(0, Math.floor((diff % 60000) / 1000));

                const timeString = `${minutesLeft.toString().padStart(2, '0')}:${secondsLeft.toString().padStart(2, '0')}`;
                countdownElement.textContent = timeString;

                // Update styling based on time remaining
                countdownContainer.className = 'stat-item countdown-timer';
                if (minutesLeft === 0 && secondsLeft <= 30) {
                    countdownContainer.classList.add('critical');
                } else if (minutesLeft === 0 && secondsLeft <= 60) {
                    countdownContainer.classList.add('warning');
                }
            }
        }).catch(error => {
            console.error('Error getting last scrape time:', error);
            countdownElement.textContent = '--:--';
        });
    }

    async getLastScrapeTime() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            return data.last_scrape_time;
        } catch (error) {
            console.error('Error fetching stats:', error);
            return null;
        }
    }

    setupNotifications() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    showNotification(title, message, type = 'info') {
        if (!this.settings.notificationsEnabled) return;

        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, {
                body: message,
                icon: '/static/favicon.ico'
            });
        }

        this.showToast(message, type);
    }

    showToast(message, type = 'info', duration = 5000) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        toast.innerHTML = `
            <i class="fas ${icons[type]} toast-icon"></i>
            <div class="toast-content">
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        `;

        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            toast.remove();
        });

        container.appendChild(toast);

        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, duration);
    }

    playNotificationSound() {
        if (!this.settings.soundEnabled) return;

        // Create a simple beep sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    }

    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        if (show) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }

    hideLoading() {
        this.showLoading(false);
    }

    filterHistory(searchTerm) {
        const items = document.querySelectorAll('.history-item');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            const matches = text.includes(searchTerm.toLowerCase());
            item.style.display = matches ? 'block' : 'none';
        });
    }

    loadSettings() {
        const saved = localStorage.getItem('pinnacle-odds-settings');
        if (saved) {
            this.settings = { ...this.settings, ...JSON.parse(saved) };
        }

        // Apply settings to UI
        document.getElementById('change-threshold').value = this.settings.changeThreshold;
        document.getElementById('auto-refresh').value = this.settings.autoRefresh;
        document.getElementById('notifications-enabled').checked = this.settings.notificationsEnabled;
        document.getElementById('sound-enabled').checked = this.settings.soundEnabled;
        document.getElementById('odds-format').value = this.settings.oddsFormat;
        document.getElementById('timezone').value = this.settings.timezone;
    }

    saveSettings() {
        localStorage.setItem('pinnacle-odds-settings', JSON.stringify(this.settings));
    }

    resetSettings() {
        // Reset to default settings
        this.settings = {
            changeThreshold: 5,
            autoRefresh: 30,
            notificationsEnabled: true,
            soundEnabled: true,
            oddsFormat: 'american',
            timezone: 'UTC'
        };
        
        // Apply default settings to UI
        this.loadSettings();
        
        // Restart auto refresh with new settings
        this.startAutoRefresh();
        
        // Reload odds with new format
        this.loadOdds();
    }

    async showPriceHistory(change) {
        try {
            // Fetch price history
            const response = await fetch(`/api/price-history/${change.event_id}?market_id=${change.market_id}&team_name=${encodeURIComponent(change.team_name)}&hours=24`);
            const data = await response.json();
            
            if (data.history && data.history.length > 0) {
                // Update pane title
                document.getElementById('pane-title').textContent = 
                    `${change.home_team} vs ${change.away_team} - ${change.team_name}`;
                
                // Create chart
                this.createPriceChart(data.history);
                
                // Populate table
                this.populatePriceHistoryTable(data.history);
                
                // Show pane
                document.getElementById('price-history-pane').classList.add('open');
                document.querySelector('.main-content').classList.add('pane-open');
            } else {
                this.showToast('No price history available for this selection', 'warning');
            }
        } catch (error) {
            console.error('Error fetching price history:', error);
            this.showToast('Failed to load price history', 'error');
        }
    }

    createPriceChart(history) {
        const ctx = document.getElementById('price-chart').getContext('2d');
        
        // Destroy existing chart if it exists
        if (this.priceChart) {
            this.priceChart.destroy();
        }
        
        const labels = history.map(item => {
            const date = new Date(item.scraped_at);
            return date.toLocaleTimeString() + ' ' + date.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit' });
        });
        
        const prices = history.map(item => item.odds_value);
        const limits = history.map(item => item.bet_limit || 100); // Use actual bet limits or default to 100
        
        this.priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                        datasets: [
                            {
                                label: 'Price',
                                data: prices,
                                borderColor: '#00ff88',
                                backgroundColor: 'rgba(0, 255, 136, 0.1)',
                                borderWidth: 2,
                                fill: false,
                                tension: 0.1,
                                pointRadius: 0,
                                pointHoverRadius: 0
                            },
                            {
                                label: 'Limit',
                                data: limits,
                                borderColor: '#ffaa00',
                                backgroundColor: 'rgba(255, 170, 0, 0.1)',
                                borderWidth: 2,
                                fill: false,
                                borderDash: [5, 5],
                                pointRadius: 0,
                                pointHoverRadius: 0
                            }
                        ]
            },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    color: '#ffffff'
                                }
                            }
                        },
                scales: {
                    x: {
                        ticks: {
                            color: '#ffffff',
                            maxTicksLimit: 3
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    },
                    y: {
                        ticks: {
                            color: '#ffffff'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    }
                }
            }
        });
    }

    populatePriceHistoryTable(history) {
        const tbody = document.getElementById('price-history-tbody');
        tbody.innerHTML = '';
        
        // Sort history by scraped_at in descending order (newest first)
        const sortedHistory = [...history].sort((a, b) => 
            new Date(b.scraped_at) - new Date(a.scraped_at)
        );
        
        sortedHistory.forEach(item => {
            const row = document.createElement('tr');
            const date = new Date(item.scraped_at);
            const timeString = date.toLocaleTimeString() + ' ' + date.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit' });
            
            row.innerHTML = `
                <td>${timeString}</td>
                <td>${this.formatOdds(item.odds_value)}</td>
                <td>${item.bet_limit || 'N/A'}</td>
            `;
            
            tbody.appendChild(row);
        });
    }

    closePriceHistoryPane() {
        document.getElementById('price-history-pane').classList.remove('open');
        document.querySelector('.main-content').classList.remove('pane-open');
        if (this.priceChart) {
            this.priceChart.destroy();
            this.priceChart = null;
        }
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PinnacleOddsApp();
});
