/* NewCo Charts - Search */

window.NewCoSearch = {
  index: null,
  naicsNames: null,

  async init(options) {
    options = options || {};
    var dataBase = options.dataBase || '../data/search/';

    // Resolve site root from nav.js script for page links
    var scripts = document.querySelectorAll('script[src*="nav.js"]');
    var siteRoot = '';
    if (scripts.length > 0) {
      var src = scripts[0].getAttribute('src');
      siteRoot = src.replace(/js\/nav\.js$/, '');
    }
    this.siteRoot = siteRoot;

    try {
      var resp = await Promise.all([
        fetch(dataBase + 'search_index.json'),
        fetch(dataBase + 'naics_names.json')
      ]);
      this.index = await resp[0].json();
      this.naicsNames = await resp[1].json();
    } catch (e) {
      document.getElementById('search-results').innerHTML =
        '<div class="search-empty">Failed to load search index.</div>';
      return;
    }

    // Check URL for query parameter
    var params = new URLSearchParams(window.location.search);
    var q = params.get('q');
    var input = document.getElementById('search-input');
    if (q) {
      input.value = q;
      this.search(q);
    }

    // Sync nav search input if present
    var navInput = document.getElementById('nav-search-input');
    if (navInput && q) {
      navInput.value = q;
    }

    // Listen for input
    var self = this;
    var debounce;
    input.addEventListener('input', function() {
      clearTimeout(debounce);
      debounce = setTimeout(function() { self.search(input.value); }, 200);
    });

    // Also handle Enter key
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        clearTimeout(debounce);
        self.search(input.value);
      }
    });
  },

  search: function(query) {
    var q = query.trim().toLowerCase();
    if (!q) {
      document.getElementById('search-results').innerHTML = '';
      document.getElementById('search-hint').textContent = '';
      // Update URL
      var url = new URL(window.location);
      url.searchParams.delete('q');
      history.replaceState(null, '', url);
      return;
    }

    // Update URL
    var url = new URL(window.location);
    url.searchParams.set('q', query.trim());
    history.replaceState(null, '', url);

    // Determine if query looks like a NAICS code (all digits)
    var isNaicsQuery = /^\d{2,6}$/.test(q);
    var results;
    var hint = document.getElementById('search-hint');

    if (isNaicsQuery) {
      // NAICS prefix match
      results = this.index.filter(function(entry) {
        return entry.naics && entry.naics.indexOf(q) === 0;
      });

      // Also include keyword matches not already found
      var resultIds = {};
      results.forEach(function(r) { resultIds[r.id + '|' + r.page] = true; });
      var keywordResults = this.index.filter(function(entry) {
        if (resultIds[entry.id + '|' + entry.page]) return false;
        return entry.name.toLowerCase().indexOf(q) !== -1;
      });
      results = results.concat(keywordResults);

      var naicsLabel = this.naicsNames[q];
      hint.textContent = naicsLabel ? 'NAICS ' + q + ': ' + naicsLabel : '';
    } else {
      // Keyword search: all terms must appear in name, naicsName, or sectionLabel
      var terms = q.split(/\s+/).filter(function(t) { return t.length > 0; });
      results = this.index.filter(function(entry) {
        var haystack = (entry.name + ' ' + (entry.naicsName || '') + ' ' +
                        entry.sectionLabel + ' ' + (entry.naics || '')).toLowerCase();
        return terms.every(function(term) {
          return haystack.indexOf(term) !== -1;
        });
      });
      hint.textContent = '';
    }

    this.renderResults(results, q);
  },

  renderResults: function(results, query) {
    var container = document.getElementById('search-results');

    if (results.length === 0) {
      container.innerHTML = '<div class="search-empty">No results found.</div>';
      return;
    }

    // Deduplicate: group entries by series id, merge pages
    var seriesMap = {};
    var seriesOrder = [];
    results.forEach(function(r) {
      if (!seriesMap[r.id + '|' + r.sectionLabel]) {
        seriesMap[r.id + '|' + r.sectionLabel] = {
          id: r.id,
          name: r.name,
          naics: r.naics,
          naicsName: r.naicsName,
          section: r.section,
          sectionLabel: r.sectionLabel,
          pages: []
        };
        seriesOrder.push(r.id + '|' + r.sectionLabel);
      }
      var existing = seriesMap[r.id + '|' + r.sectionLabel];
      var alreadyHasPage = existing.pages.some(function(p) { return p.page === r.page; });
      if (!alreadyHasPage) {
        existing.pages.push({ page: r.page, pageLabel: r.pageLabel });
      }
    });

    // Group by section
    var groups = {};
    var groupOrder = [];
    var self = this;
    seriesOrder.forEach(function(key) {
      var item = seriesMap[key];
      if (!groups[item.sectionLabel]) {
        groups[item.sectionLabel] = [];
        groupOrder.push(item.sectionLabel);
      }
      groups[item.sectionLabel].push(item);
    });

    var uniqueCount = seriesOrder.length;
    var html = '<div class="search-count">' + uniqueCount + ' series found</div>';

    groupOrder.forEach(function(section) {
      var items = groups[section];
      html += '<div class="search-group">';
      html += '<h2 class="search-group-title">' + section + ' (' + items.length + ')</h2>';

      items.forEach(function(item) {
        var naicsBadge = item.naics
          ? '<span class="naics-badge">NAICS ' + item.naics + '</span>'
          : '';
        var links = item.pages.map(function(p) {
          return '<a href="' + self.siteRoot + p.page + '" class="result-link">' + p.pageLabel + '</a>';
        }).join('');

        html += '<div class="search-result">';
        html += '<div class="result-name">' + self.highlight(item.name, query) + '</div>';
        html += naicsBadge;
        html += '<div class="result-links">' + links + '</div>';
        html += '</div>';
      });

      html += '</div>';
    });

    container.innerHTML = html;
  },

  highlight: function(text, query) {
    var terms = query.toLowerCase().split(/\s+/).filter(function(t) { return t.length > 0; });
    var result = text;
    terms.forEach(function(term) {
      var escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      var regex = new RegExp('(' + escaped + ')', 'gi');
      result = result.replace(regex, '<mark>$1</mark>');
    });
    return result;
  }
};

// Initialized by page script calling NewCoSearch.init({ dataBase: '...' })
