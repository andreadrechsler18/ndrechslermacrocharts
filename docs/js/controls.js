/* NewCo Charts - Controls (Raw/YoY Toggle + Time Horizon + Category) */

window.NewCoControls = {
  mode: 'yoy',
  horizon: 24,

  init(container, options) {
    this.container = container;
    this.mode = options.mode || 'yoy';
    this.horizon = options.horizon || 24;
    this.baseModes = options.modes || [
      { key: 'raw', label: 'Raw Data' },
      { key: 'yoy', label: 'YoY % Change' }
    ];
    this.modes = [...this.baseModes];

    // Category support (e.g. Durable Goods / Nondurable Goods / Services)
    this.categories = options.categories || null;
    this.activeCategory = null;

    // Read from URL hash if present
    this.readHash();

    const modeButtons = this.modes.map(m =>
      '<button data-mode="' + m.key + '" class="' + (this.mode === m.key ? 'active' : '') + '">' + m.label + '</button>'
    ).join('');

    // Optional category buttons
    let categoryHtml = '';
    if (this.categories) {
      const catButtons = this.categories.map(c =>
        '<button data-category="' + c.key + '">' + c.label + '</button>'
      ).join('');
      categoryHtml =
        '<div class="control-group">' +
          '<span class="control-label">Category:</span>' +
          '<div class="btn-group" id="category-toggle">' +
            '<button data-category="" class="active">All</button>' +
            catButtons +
          '</div>' +
        '</div>';
    }

    // Optional filter buttons
    this.filters = options.filters || null;
    this.activeFilter = null;
    this.filterGroups = null;
    this.activeFilterGroup = null;
    let filterHtml = '';
    if (this.filters) {
      // Check if filters use separator groups (e.g. Current / Future)
      const hasSeparators = this.filters.some(f => f.separator);

      if (hasSeparators) {
        // Split into groups by separator
        this.filterGroups = {};
        let currentGroup = null;
        this.filters.forEach(f => {
          if (f.separator) {
            currentGroup = f.separator;
            this.filterGroups[currentGroup] = [];
          } else if (currentGroup) {
            this.filterGroups[currentGroup].push(f);
          }
        });
        const groupNames = Object.keys(this.filterGroups);
        this.activeFilterGroup = groupNames[0] || null;

        // Timing toggle
        const timingButtons = groupNames.map(g =>
          '<button data-timing="' + g + '" class="' + (g === this.activeFilterGroup ? 'active' : '') + '">' + g + '</button>'
        ).join('');
        const timingHtml =
          '<div class="control-group">' +
            '<span class="control-label">Timing:</span>' +
            '<div class="btn-group" id="timing-toggle">' + timingButtons + '</div>' +
          '</div>';

        // Filter buttons for active group
        const activeFilters = this.filterGroups[this.activeFilterGroup] || [];
        const filterButtons = activeFilters.map(f =>
          '<button data-filter="' + f.key + '">' + f.label + '</button>'
        ).join('');
        filterHtml = timingHtml +
          '<div class="control-group">' +
            '<span class="control-label">Component:</span>' +
            '<div class="btn-group" id="filter-toggle">' +
              '<button data-filter="" class="active">All</button>' +
              filterButtons +
            '</div>' +
          '</div>';
      } else {
        const filterButtons = this.filters.map(f =>
          '<button data-filter="' + f.key + '">' + f.label + '</button>'
        ).join('');
        filterHtml =
          '<div class="control-group">' +
            '<span class="control-label">Filter:</span>' +
            '<div class="btn-group" id="filter-toggle">' +
              '<button data-filter="" class="active">All</button>' +
              filterButtons +
            '</div>' +
          '</div>';
      }
    }

    // Optional city filter buttons
    this.cityFilters = options.cityFilters || null;
    this.activeCity = null;
    let cityHtml = '';
    if (this.cityFilters) {
      const cityButtons = this.cityFilters.map(c =>
        '<button data-city="' + c.key + '">' + c.label + '</button>'
      ).join('');
      cityHtml =
        '<div class="control-group">' +
          '<span class="control-label">City:</span>' +
          '<div class="btn-group" id="city-toggle">' +
            '<button data-city="" class="active">All</button>' +
            cityButtons +
          '</div>' +
        '</div>';
    }

    container.innerHTML =
      categoryHtml +
      '<div class="control-group">' +
        '<span class="control-label">View:</span>' +
        '<div class="btn-group" id="mode-toggle">' + modeButtons + '</div>' +
      '</div>' +
      filterHtml +
      cityHtml +
      '<div class="control-group">' +
        '<span class="control-label">Horizon:</span>' +
        '<div class="btn-group" id="horizon-toggle">' +
          '<button data-horizon="12" class="' + (this.horizon === 12 ? 'active' : '') + '">1Y</button>' +
          '<button data-horizon="24" class="' + (this.horizon === 24 ? 'active' : '') + '">2Y</button>' +
          '<button data-horizon="60" class="' + (this.horizon === 60 ? 'active' : '') + '">5Y</button>' +
          '<button data-horizon="120" class="' + (this.horizon === 120 ? 'active' : '') + '">10Y</button>' +
          '<button data-horizon="0" class="' + (this.horizon === 0 ? 'active' : '') + '">Max</button>' +
        '</div>' +
      '</div>';

    // Mode toggle (uses event delegation so dynamic button updates work)
    container.querySelector('#mode-toggle').addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (!btn) return;
      const newMode = btn.dataset.mode;
      if (newMode === this.mode) return;
      this.mode = newMode;
      this.updateButtons(container.querySelector('#mode-toggle'), 'mode', newMode);
      this.updateHash();
      document.dispatchEvent(new CustomEvent('modechange', { detail: newMode }));
    });

    // Horizon toggle
    container.querySelector('#horizon-toggle').addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (!btn) return;
      const newHorizon = parseInt(btn.dataset.horizon, 10);
      if (newHorizon === this.horizon) return;
      this.horizon = newHorizon;
      this.updateButtons(container.querySelector('#horizon-toggle'), 'horizon', String(newHorizon));
      this.updateHash();
      document.dispatchEvent(new CustomEvent('horizonchange', { detail: newHorizon }));
    });

    // Category toggle
    const catToggle = container.querySelector('#category-toggle');
    if (catToggle) {
      catToggle.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        const catKey = btn.dataset.category || null;
        const currentKey = this.activeCategory ? this.activeCategory.key : null;
        if (catKey === currentKey) return;

        this.activeCategory = catKey ? this.categories.find(c => c.key === catKey) : null;
        this.updateButtons(catToggle, 'category', btn.dataset.category);
        this.updateModeButtons();
        document.dispatchEvent(new CustomEvent('categorychange', { detail: this.activeCategory }));
      });
    }

    // Timing toggle (switches which filter group is shown)
    const timingToggle = container.querySelector('#timing-toggle');
    if (timingToggle) {
      timingToggle.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        const newTiming = btn.dataset.timing;
        if (newTiming === this.activeFilterGroup) return;
        this.activeFilterGroup = newTiming;
        this.updateButtons(timingToggle, 'timing', newTiming);
        // Reset active filter and rebuild filter buttons
        this.activeFilter = null;
        this.rebuildFilterButtons();
        document.dispatchEvent(new CustomEvent('filterchange', { detail: null }));
      });
    }

    // Filter toggle
    const filterToggle = container.querySelector('#filter-toggle');
    if (filterToggle) {
      filterToggle.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        const newFilter = btn.dataset.filter || null;
        if (newFilter === this.activeFilter) return;
        this.activeFilter = newFilter;
        this.updateButtons(filterToggle, 'filter', btn.dataset.filter);
        document.dispatchEvent(new CustomEvent('filterchange', { detail: newFilter }));
      });
    }

    // City toggle
    const cityToggle = container.querySelector('#city-toggle');
    if (cityToggle) {
      cityToggle.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        const newCity = btn.dataset.city || null;
        if (newCity === this.activeCity) return;
        this.activeCity = newCity;
        this.updateButtons(cityToggle, 'city', btn.dataset.city);
        document.dispatchEvent(new CustomEvent('citychange', { detail: newCity }));
      });
    }
  },

  updateModeButtons() {
    const modes = [...this.baseModes];
    if (this.activeCategory) {
      modes.push({ key: 'share', label: 'Share of ' + this.activeCategory.label });
    } else if (this.mode === 'share') {
      // Switching back to All — share mode no longer available
      this.mode = 'yoy';
      this.updateHash();
      document.dispatchEvent(new CustomEvent('modechange', { detail: this.mode }));
    }
    this.modes = modes;

    const modeToggle = this.container.querySelector('#mode-toggle');
    if (modeToggle) {
      modeToggle.innerHTML = modes.map(m =>
        '<button data-mode="' + m.key + '" class="' + (this.mode === m.key ? 'active' : '') + '">' + m.label + '</button>'
      ).join('');
    }
  },

  rebuildFilterButtons() {
    const filterToggle = this.container.querySelector('#filter-toggle');
    if (!filterToggle || !this.filterGroups) return;
    const filters = this.filterGroups[this.activeFilterGroup] || [];
    filterToggle.innerHTML =
      '<button data-filter="" class="active">All</button>' +
      filters.map(f =>
        '<button data-filter="' + f.key + '">' + f.label + '</button>'
      ).join('');
  },

  updateButtons(group, attr, value) {
    group.querySelectorAll('button').forEach(b => {
      b.classList.toggle('active', b.dataset[attr] === value);
    });
  },

  readHash() {
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    const params = new URLSearchParams(hash);
    if (params.has('mode')) this.mode = params.get('mode');
    if (params.has('horizon')) this.horizon = parseInt(params.get('horizon'), 10);
  },

  updateHash() {
    const params = new URLSearchParams();
    params.set('mode', this.mode);
    params.set('horizon', String(this.horizon));
    window.location.hash = params.toString();
  }
};
