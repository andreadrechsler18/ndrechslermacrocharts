/* NewCo Charts - Core Chart Rendering Engine */

window.NewCoCharts = {
  data: null,
  mode: 'yoy',
  horizon: 24,
  chartElements: [],
  rendered: new Set(),

  async init(options) {
    this.mode = options.defaultMode || 'yoy';
    this.horizon = options.defaultHorizon || 24;
    this.totalSeriesIndex = options.totalSeriesIndex != null ? options.totalSeriesIndex : null;
    this.modes = options.modes || null;
    this.filters = options.filters || null;
    this.filterType = options.filterType || 'prefix';
    this.excludePatterns = options.excludePatterns || null;
    this.chartType = options.chartType || null; // 'bar' or 'line' to override default
    this.excludeFromTotalIndex = options.excludeFromTotalIndex != null ? options.excludeFromTotalIndex : null;
    this.categories = options.categories || null;
    this.activeCategory = null;
    this.categoryTotalIndex = null;
    this.cityFilters = options.cityFilters || null;
    this.activeCity = null;

    // Show loading state
    const grid = document.getElementById('chart-grid');
    grid.innerHTML = '<div class="chart-loading" style="grid-column:1/-1">Loading data...</div>';

    // Fetch JSON data
    try {
      const resp = await fetch(options.dataUrl);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      this.data = await resp.json();
    } catch (err) {
      grid.innerHTML = '<div class="chart-error" style="grid-column:1/-1">Failed to load data: ' + err.message + '</div>';
      return;
    }

    // Generate computed series (e.g. subtract one series from another)
    if (options.computedSeries) {
      options.computedSeries.forEach(cs => {
        const a = this.data.series[cs.sources[0]];
        const b = this.data.series[cs.sources[1]];
        if (!a || !b) return;
        const bMap = {};
        b.data.forEach(d => { bMap[d.date] = d.value; });
        const data = a.data.map(d => ({
          date: d.date,
          value: (d.value != null && bMap[d.date] != null) ? d.value - bMap[d.date] : null
        }));
        this.data.series.push({ id: cs.id, name: cs.name, data: data });
      });
    }

    // Build series ID to array index map (for category total lookups)
    this.seriesIdMap = {};
    this.data.series.forEach((s, i) => { this.seriesIdMap[s.id] = i; });

    // Update page title from data
    const pageTitle = document.querySelector('.page-header h1');
    if (pageTitle && this.data.metadata.title) {
      pageTitle.textContent = this.data.metadata.title;
    }

    // Initialize controls
    const controlsEl = document.getElementById('chart-controls');
    if (controlsEl) {
      const controlOpts = { mode: this.mode, horizon: this.horizon };
      if (this.modes) controlOpts.modes = this.modes;
      if (this.filters) controlOpts.filters = this.filters;
      if (this.categories) controlOpts.categories = this.categories;
      if (this.cityFilters) controlOpts.cityFilters = this.cityFilters;
      NewCoControls.init(controlsEl, controlOpts);
      this.mode = NewCoControls.mode;
      this.horizon = NewCoControls.horizon;
    }

    // Create chart cards
    grid.innerHTML = '';
    this.chartElements = [];

    this.data.series.forEach((series, i) => {
      // Skip permanently excluded series
      if (this.excludePatterns && this.excludePatterns.some(pat => series.id.includes(pat))) {
        this.chartElements.push(null);
        return;
      }

      const card = document.createElement('div');
      card.className = 'chart-card';
      card.dataset.seriesIndex = i;
      card.dataset.seriesId = series.id;
      card.innerHTML =
        '<div class="chart-title">' + this.escapeHtml(series.name) + '</div>' +
        '<div class="chart-container" id="chart-' + i + '">' +
        '<div class="chart-loading">Loading...</div>' +
        '</div>';
      grid.appendChild(card);
      this.chartElements.push(card);
    });

    // Initialize lazy loading
    NewCoLazyLoad.init((idx) => this.renderChart(idx));

    // Apply initial mode visibility
    this.applyModeVisibility();

    // Apply initial filter for pages with filter groups (e.g. Current/Future timing)
    if (NewCoControls.filterGroups) {
      this.activeFilter = NewCoControls.getGroupFilter();
    }
    // Apply visibility (populates grid with matching cards and starts observation)
    this.applyVisibility();

    // Listen for control changes
    document.addEventListener('modechange', (e) => {
      this.mode = e.detail;
      this.applyModeVisibility();
      this.reRenderVisible();
    });

    document.addEventListener('horizonchange', (e) => {
      this.horizon = e.detail;
      this.reRenderVisible();
    });

    document.addEventListener('filterchange', (e) => {
      this.activeFilter = e.detail;
      this.applyVisibility();
    });

    document.addEventListener('citychange', (e) => {
      this.activeCity = e.detail;
      this.applyVisibility();
    });

    document.addEventListener('categorychange', (e) => {
      this.applyCategory(e.detail);
    });
  },

  waitForPlotly() {
    if (typeof Plotly !== 'undefined') return Promise.resolve();
    return new Promise(resolve => {
      const check = setInterval(() => {
        if (typeof Plotly !== 'undefined') {
          clearInterval(check);
          resolve();
        }
      }, 50);
    });
  },

  async renderChart(index) {
    const card = this.chartElements[index];
    // Skip if card is not in the DOM (filtered out)
    if (!card || !card.isConnected) return;

    const series = this.data.series[index];
    if (!series || !series.data || series.data.length === 0) return;

    await this.waitForPlotly();

    const containerId = 'chart-' + index;
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('[NewCo] renderChart: container not found for', containerId);
      return;
    }

    console.log('[NewCo] renderChart: rendering index', index, 'series', series.id);

    const plotData = this.prepareData(series);

    try {
      Plotly.newPlot(container, [plotData.trace], plotData.layout, {
        responsive: true,
        displayModeBar: false
      });
    } catch (err) {
      console.error('[NewCo] Plotly.newPlot failed for index', index, err);
      return;
    }

    // Remove loading text if Plotly didn't replace it
    const loading = container.querySelector('.chart-loading');
    if (loading) loading.remove();

    this.rendered.add(index);
  },

  prepareData(series) {
    const rawDates = series.data.map(d => d.date);
    const rawValues = series.data.map(d => d.value);
    let dates, values, yLabel;

    if (this.mode === 'share' && this.categoryTotalIndex != null) {
      // Compute % share of category total
      const totalSeries = this.data.series[this.categoryTotalIndex];
      const totalMap = {};
      totalSeries.data.forEach(d => { totalMap[d.date] = d.value; });

      dates = [];
      values = [];
      for (let i = 0; i < rawDates.length; i++) {
        const totalVal = totalMap[rawDates[i]];
        dates.push(rawDates[i]);
        if (rawValues[i] == null || totalVal == null || totalVal === 0) {
          values.push(null);
        } else {
          values.push((rawValues[i] / totalVal) * 100);
        }
      }
      yLabel = '% Share';
    } else if (this.mode === 'pct' && this.totalSeriesIndex != null) {
      // Compute % of total
      const totalSeries = this.data.series[this.totalSeriesIndex];
      const totalMap = {};
      totalSeries.data.forEach(d => { totalMap[d.date] = d.value; });

      dates = [];
      values = [];
      for (let i = 0; i < rawDates.length; i++) {
        const totalVal = totalMap[rawDates[i]];
        dates.push(rawDates[i]);
        if (rawValues[i] == null || totalVal == null || totalVal === 0) {
          values.push(null);
        } else {
          values.push((rawValues[i] / totalVal) * 100);
        }
      }
      yLabel = '% of Total';
    } else if (this.mode === 'pct_ex' && this.totalSeriesIndex != null && this.excludeFromTotalIndex != null) {
      // Compute % of (total minus excluded series)
      const totalSeries = this.data.series[this.totalSeriesIndex];
      const excludeSeries = this.data.series[this.excludeFromTotalIndex];
      const totalMap = {};
      totalSeries.data.forEach(d => { totalMap[d.date] = d.value; });
      const excludeMap = {};
      excludeSeries.data.forEach(d => { excludeMap[d.date] = d.value; });

      dates = [];
      values = [];
      for (let i = 0; i < rawDates.length; i++) {
        const totalVal = totalMap[rawDates[i]];
        const excludeVal = excludeMap[rawDates[i]];
        dates.push(rawDates[i]);
        if (rawValues[i] == null || totalVal == null || excludeVal == null || (totalVal - excludeVal) === 0) {
          values.push(null);
        } else {
          values.push((rawValues[i] / (totalVal - excludeVal)) * 100);
        }
      }
      yLabel = '% of Total ex. Excluded';
    } else if (this.mode === 'spread' && this.totalSeriesIndex != null) {
      // Compute spread vs aggregate (series value minus total value)
      const totalSeries = this.data.series[this.totalSeriesIndex];
      const totalMap = {};
      totalSeries.data.forEach(d => { totalMap[d.date] = d.value; });

      dates = [];
      values = [];
      for (let i = 0; i < rawDates.length; i++) {
        const totalVal = totalMap[rawDates[i]];
        dates.push(rawDates[i]);
        if (rawValues[i] == null || totalVal == null) {
          values.push(null);
        } else {
          values.push(rawValues[i] - totalVal);
        }
      }
      yLabel = 'Spread vs Aggregate (pp)';
    } else if (this.mode === 'pop' || this.mode === 'pop3') {
      // Period-over-period change (current minus previous)
      const popDates = [];
      const popValues = [];
      for (let i = 1; i < rawDates.length; i++) {
        popDates.push(rawDates[i]);
        if (rawValues[i] == null || rawValues[i - 1] == null) {
          popValues.push(null);
        } else {
          popValues.push(rawValues[i] - rawValues[i - 1]);
        }
      }

      if (this.mode === 'pop3') {
        // Trailing 3-month sum of PoP changes
        dates = [];
        values = [];
        for (let i = 2; i < popDates.length; i++) {
          dates.push(popDates[i]);
          const v0 = popValues[i], v1 = popValues[i - 1], v2 = popValues[i - 2];
          if (v0 == null || v1 == null || v2 == null) {
            values.push(null);
          } else {
            values.push(v0 + v1 + v2);
          }
        }
        yLabel = 'Trailing 3-Month Change';
      } else {
        dates = popDates;
        values = popValues;
        yLabel = 'Period over Period Change';
      }
    } else if (this.mode === 'raw') {
      dates = rawDates;
      values = rawValues;
      yLabel = this.data.metadata.unit || 'Value';
    } else {
      // Compute YoY % change
      const freq = this.data.metadata.frequency;
      const lookback = (freq === 'quarterly') ? 4 : 12;
      dates = [];
      values = [];

      for (let i = lookback; i < rawDates.length; i++) {
        const current = rawValues[i];
        const previous = rawValues[i - lookback];
        dates.push(rawDates[i]);

        if (current == null || previous == null || previous === 0) {
          values.push(null);
        } else {
          values.push(((current - previous) / Math.abs(previous)) * 100);
        }
      }
      yLabel = 'YoY % Change';
    }

    // Apply time horizon filter
    if (this.horizon > 0 && dates.length > 0) {
      const lastDate = new Date(dates[dates.length - 1]);
      const cutoff = new Date(lastDate);
      cutoff.setMonth(cutoff.getMonth() - this.horizon);
      const cutoffStr = cutoff.toISOString().slice(0, 10);

      const startIdx = dates.findIndex(d => d >= cutoffStr);
      if (startIdx > 0) {
        dates = dates.slice(startIdx);
        values = values.slice(startIdx);
      }
    }

    // Color bars: positive = blue, negative = red-ish
    const colors = values.map(v =>
      v == null ? '#ccc' : (v >= 0 ? '#4a90d9' : '#e74c3c')
    );

    const isLine = this.chartType === 'bar' ? false :
      this.chartType === 'line' ? true :
      (this.mode === 'raw' || this.mode === 'pct' || this.mode === 'pct_ex' || this.mode === 'spread' || this.mode === 'share');

    return {
      trace: isLine ? {
        x: dates,
        y: values,
        type: 'scatter',
        mode: 'lines',
        line: { color: '#4a90d9', width: 2 },
        hovertemplate: '%{x|%b %Y}: %{y:.2f}<extra></extra>'
      } : {
        x: dates,
        y: values,
        type: 'bar',
        marker: { color: colors },
        hovertemplate: '%{x|%b %Y}: %{y:.2f}<extra></extra>'
      },
      layout: {
        margin: { t: 4, r: 8, b: 40, l: 50 },
        xaxis: {
          type: 'date',
          tickformat: '%b\n%Y',
          tickangle: 0,
          tickfont: { size: 9 },
          gridcolor: '#f0f0f0'
        },
        yaxis: {
          title: { text: yLabel, font: { size: 9 } },
          tickfont: { size: 9 },
          gridcolor: '#f0f0f0',
          zeroline: true,
          zerolinecolor: '#999',
          zerolinewidth: 1
        },
        height: 230,
        plot_bgcolor: '#fff',
        paper_bgcolor: '#fff',
        font: { family: 'Segoe UI, Roboto, sans-serif' }
      }
    };
  },

  applyModeVisibility() {
    // Hide denominator series in percentage modes
    if (this.totalSeriesIndex != null) {
      const totalCard = this.chartElements[this.totalSeriesIndex];
      if (totalCard) totalCard.style.display = (this.mode === 'pct' || this.mode === 'pct_ex') ? 'none' : '';
    }
    if (this.excludeFromTotalIndex != null) {
      const exCard = this.chartElements[this.excludeFromTotalIndex];
      if (exCard) exCard.style.display = (this.mode === 'pct_ex') ? 'none' : '';
    }
  },

  applyFilter(filterKey) {
    this.activeFilter = filterKey;
    this.applyVisibility();
  },

  applyVisibility() {
    const filterKey = this.activeFilter;
    const cityKey = this.activeCity;
    const grid = document.getElementById('chart-grid');

    // Remove all cards from the DOM (references kept in chartElements)
    while (grid.firstChild) {
      grid.removeChild(grid.firstChild);
    }

    // Re-append only matching cards
    this.chartElements.forEach(card => {
      if (!card) return;
      const sid = card.dataset.seriesId;

      // Check filter (component) match
      let filterMatch = true;
      if (filterKey) {
        if (this.filterType === 'suffix') {
          const suffixes = filterKey.split(',');
          filterMatch = sid && suffixes.some(s => sid.endsWith(s));
        } else {
          filterMatch = sid && sid.startsWith(filterKey);
        }
      }

      // Check city match (prefix-based)
      let cityMatch = true;
      if (cityKey) {
        cityMatch = sid && sid.startsWith(cityKey);
      }

      // Also respect mode visibility (e.g. hidden total series)
      if (filterMatch && cityMatch && card.style.display !== 'none') {
        grid.appendChild(card);
      }
    });

    console.log('[NewCo v2] applyVisibility: filter=' + filterKey + ' city=' + cityKey + ' cards_in_grid=' + grid.children.length);

    // Queue unrendered visible cards for rendering
    NewCoLazyLoad.renderQueue = [];
    this.chartElements.forEach(el => {
      if (el && el.isConnected) {
        const idx = parseInt(el.dataset.seriesIndex, 10);
        if (!this.rendered.has(idx)) {
          NewCoLazyLoad.renderQueue.push(idx);
        }
        NewCoLazyLoad.observe(el);
      }
    });
    if (NewCoLazyLoad.renderQueue.length > 0 && !NewCoLazyLoad.rendering) {
      NewCoLazyLoad.processBatch();
    }

    requestAnimationFrame(() => {
      this.reRenderVisible();
    });
  },

  applyCategory(category) {
    this.activeCategory = category;
    const grid = document.getElementById('chart-grid');

    // Remove all cards from the DOM
    while (grid.firstChild) {
      grid.removeChild(grid.firstChild);
    }

    if (!category) {
      // Show all charts
      this.categoryTotalIndex = null;
      this.chartElements.forEach(card => { if (card) grid.appendChild(card); });
    } else {
      // Set the category total series for share calculations
      this.categoryTotalIndex = this.seriesIdMap[category.totalId] ?? null;

      // Parse ID range boundaries
      const startNum = parseInt(category.range[0].split('_').pop(), 10);
      const endNum = parseInt(category.range[1].split('_').pop(), 10);

      this.chartElements.forEach(card => {
        if (!card) return;
        const sid = card.dataset.seriesId;
        const num = parseInt(sid.split('_').pop(), 10);
        if (num >= startNum && num <= endNum) {
          grid.appendChild(card);
        }
      });
    }

    // Queue unrendered visible cards for rendering
    NewCoLazyLoad.renderQueue = [];
    this.chartElements.forEach(el => {
      if (el && el.isConnected) {
        const idx = parseInt(el.dataset.seriesIndex, 10);
        if (!this.rendered.has(idx)) {
          NewCoLazyLoad.renderQueue.push(idx);
        }
        NewCoLazyLoad.observe(el);
      }
    });
    if (NewCoLazyLoad.renderQueue.length > 0 && !NewCoLazyLoad.rendering) {
      NewCoLazyLoad.processBatch();
    }

    requestAnimationFrame(() => {
      this.reRenderVisible();
    });
  },

  reRenderVisible() {
    this.rendered.forEach(index => {
      const card = this.chartElements[index];
      if (!card || !card.isConnected) return;
      this.renderChart(index);
    });
  },

  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
};
