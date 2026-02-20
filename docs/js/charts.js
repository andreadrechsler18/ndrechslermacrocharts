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
    this.chartElements.forEach(el => { if (el) NewCoLazyLoad.observe(el); });

    // Listen for control changes
    document.addEventListener('modechange', (e) => {
      this.mode = e.detail;
      this.reRenderVisible();
    });

    document.addEventListener('horizonchange', (e) => {
      this.horizon = e.detail;
      this.reRenderVisible();
    });

    document.addEventListener('filterchange', (e) => {
      this.applyFilter(e.detail);
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
    const series = this.data.series[index];
    if (!series || !series.data || series.data.length === 0) return;

    await this.waitForPlotly();

    const containerId = 'chart-' + index;
    const plotData = this.prepareData(series);

    Plotly.newPlot(containerId, [plotData.trace], plotData.layout, {
      responsive: true,
      displayModeBar: false
    });

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

  applyFilter(filterKey) {
    this.chartElements.forEach(card => {
      if (!card) return;
      if (!filterKey) {
        card.style.display = '';
      } else if (this.filterType === 'suffix') {
        const sid = card.dataset.seriesId;
        const suffixes = filterKey.split(',');
        card.style.display = sid && suffixes.some(s => sid.endsWith(s)) ? '' : 'none';
      } else {
        const sid = card.dataset.seriesId;
        card.style.display = sid && sid.startsWith(filterKey) ? '' : 'none';
      }
    });
    // Re-observe visible cards so lazy loading picks them up
    this.chartElements.forEach(el => {
      if (el && el.style.display !== 'none') {
        NewCoLazyLoad.observe(el);
      }
    });

    // Defer re-rendering until browser has completed layout of newly visible cards
    requestAnimationFrame(() => {
      this.reRenderVisible();
    });
  },

  applyCategory(category) {
    this.activeCategory = category;

    if (!category) {
      // Show all charts
      this.categoryTotalIndex = null;
      this.chartElements.forEach(card => { if (card) card.style.display = ''; });
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
        card.style.display = (num >= startNum && num <= endNum) ? '' : 'none';
      });
    }

    // Re-observe visible cards so lazy loading picks them up
    this.chartElements.forEach(el => {
      if (el && el.style.display !== 'none') {
        NewCoLazyLoad.observe(el);
      }
    });

    // Defer re-rendering until browser has completed layout of newly visible cards
    requestAnimationFrame(() => {
      this.reRenderVisible();
    });
  },

  reRenderVisible() {
    this.rendered.forEach(index => {
      const card = this.chartElements[index];
      if (card && card.style.display === 'none') return;
      this.renderChart(index);
    });
  },

  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
};
