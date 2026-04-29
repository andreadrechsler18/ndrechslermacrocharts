/* NDMacroCharts - Shared Navigation */

const SITE_MAP = [
  { label: "Home", href: "index.html" },
  { label: "Search", href: "search/index.html" },
  {
    label: "NIPA Data", children: [
      { label: "1BU - Mfg & Trade Inventories", href: "nipa/1bu.html" },
      { label: "2.4.4U - PCE Deflator", href: "nipa/2_4_4u.html" },
      { label: "2.4.5U - Nominal Spending", href: "nipa/2_4_5u.html" },
      { label: "2.4.6U - Real Spending", href: "nipa/2_4_6u.html" },
      { label: "2BU - Mfg & Trade Sales", href: "nipa/2bu.html" },
      { label: "3.3 - State & Local Govt", href: "nipa/3_3.html" },
      { label: "3BU - Inventory-Sales Ratio", href: "nipa/3bu.html" },
      { label: "4.2.5B - Net Exports", href: "nipa/4_2_5b.html" },
      { label: "4.2.6B - Real Imports", href: "nipa/4_2_6b.html" },
      { label: "5.3.5 - Nonresidential Investment", href: "nipa/5_3_5.html" },
      { label: "5.5.5U - Equipment Spending", href: "nipa/5_5_5u.html" },
      { label: "5.7.5BU1 - Private Inventories", href: "nipa/5_7_5bu1.html" },
    ]
  },
  { label: "M3 - Shipments, Inventories & Orders", href: "m3/index.html" },
  {
    label: "Current Employment Statistics", children: [
      { label: "Employees - Preliminary", href: "ces/employees_preliminary.html" },
      { label: "Employees - Detailed", href: "ces/employees_detailed.html" },
      { label: "Employees - All", href: "ces/employees_long.html" },
      { label: "Prof. & Business Services", href: "ces/employees_pbs.html" },
      { label: "Aggregate Payrolls", href: "ces/payrolls.html" },
    ]
  },
  { label: "Quarterly Services Survey", href: "qss/index.html" },
  { label: "Construction Spending", href: "construction/index.html" },
  {
    label: "Monthly Wholesale Trade", children: [
      { label: "Sales", href: "wholesale/sales.html" },
      { label: "Inventories", href: "wholesale/inventory.html" },
      { label: "Inventory/Sales Ratio", href: "wholesale/ratio.html" },
      { label: "Implied Purchases", href: "wholesale/implied_purchases.html" },
    ]
  },
  { label: "Unemployment by Industry", href: "unemployment/index.html" },
  { label: "Industrial Production", href: "industrial_production/index.html" },
  {
    label: "Fed Regional Surveys", children: [
      { label: "Manufacturing", href: "fed_surveys/manufacturing.html" },
      { label: "Services", href: "fed_surveys/services.html" },
    ]
  },
  {
    label: "PPI", children: [
      { label: "Selected Services by Industry", href: "ppi/selected_services.html" },
      { label: "By Commodity", href: "ppi/commodity.html" },
    ]
  },
  {
    label: "Google Trends — Web", children: [
      { label: "Apparel", href: "google_trends/web_apparel.html" },
      { label: "Beauty", href: "google_trends/web_beauty.html" },
      { label: "Electronics", href: "google_trends/web_electronics.html" },
      { label: "Footwear", href: "google_trends/web_footwear.html" },
      { label: "Restaurants", href: "google_trends/web_restaurants.html" },
      { label: "Retail", href: "google_trends/web_retail.html" },
    ]
  },
  {
    label: "Google Trends — YouTube", children: [
      { label: "Apparel", href: "google_trends/youtube_apparel.html" },
      { label: "Beauty", href: "google_trends/youtube_beauty.html" },
      { label: "Electronics", href: "google_trends/youtube_electronics.html" },
      { label: "Footwear", href: "google_trends/youtube_footwear.html" },
      { label: "Restaurants", href: "google_trends/youtube_restaurants.html" },
      { label: "Retail", href: "google_trends/youtube_retail.html" },
    ]
  },
  {
    label: "Analysis", children: [
      { label: "AI Impact on Prof. Services", href: "analysis/ai_employment.html" },
    ]
  },
  { label: "Release Calendar", href: "calendar/index.html" },
];

(function() {
  const nav = document.getElementById('main-nav');
  if (!nav) return;

  // Find the site root by locating the nav.js script tag
  // The script is always at <siteroot>/js/nav.js
  const scripts = document.querySelectorAll('script[src*="nav.js"]');
  let siteRoot = '';
  if (scripts.length > 0) {
    const src = scripts[0].getAttribute('src');
    // src is like "../js/nav.js?v=3" or "js/nav.js" etc.
    // Strip "js/nav.js" and anything after it (query params, hash)
    siteRoot = src.replace(/js\/nav\.js.*$/, '');
  }

  function resolvePath(href) {
    return siteRoot + href;
  }

  function isActive(href) {
    const current = window.location.pathname;
    return current.endsWith(href) || current.endsWith('/' + href);
  }

  let html = '';

  // Header
  html += '<div class="nav-header"><h1><a href="' + resolvePath('index.html') + '">NDMacroCharts</a></h1></div>';

  // Search input
  html += '<div class="nav-search"><input type="text" id="nav-search-input" placeholder="Search NAICS or keyword..."></div>';

  // Build nav items
  SITE_MAP.forEach(item => {
    html += '<div class="nav-section">';

    if (item.href) {
      const cls = isActive(item.href) ? ' active' : '';
      html += '<a class="nav-link' + cls + '" href="' + resolvePath(item.href) + '">' + item.label + '</a>';
    }

    if (item.children) {
      html += '<span class="nav-parent-label">' + item.label + '</span>';
      html += '<div class="nav-children">';
      item.children.forEach(child => {
        const cls = isActive(child.href) ? ' active' : '';
        html += '<a class="nav-link' + cls + '" href="' + resolvePath(child.href) + '">' + child.label + '</a>';
      });
      html += '</div>';
    }

    html += '</div>';
  });

  nav.innerHTML = html;

  // Nav search handler
  var searchInput = nav.querySelector('#nav-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && searchInput.value.trim()) {
        window.location.href = resolvePath('search/index.html') +
          '?q=' + encodeURIComponent(searchInput.value.trim());
      }
    });
  }

  // Restore sidebar scroll position across page navigations
  var savedScroll = sessionStorage.getItem('navScrollTop');
  if (savedScroll) nav.scrollTop = parseInt(savedScroll, 10);

  nav.addEventListener('click', function(e) {
    if (e.target.closest('.nav-link')) {
      sessionStorage.setItem('navScrollTop', String(nav.scrollTop));
    }
  });

  // Mobile toggle
  const toggle = document.createElement('button');
  toggle.className = 'nav-toggle';
  toggle.textContent = '\u2630';
  toggle.addEventListener('click', () => nav.classList.toggle('open'));
  document.body.appendChild(toggle);

  // Close nav on link click (mobile)
  nav.addEventListener('click', (e) => {
    if (e.target.classList.contains('nav-link')) {
      nav.classList.remove('open');
    }
  });
})();
