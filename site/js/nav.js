/* NewCo Charts - Shared Navigation */

const SITE_MAP = [
  { label: "Home", href: "index.html" },
  {
    label: "NIPA Data", children: [
      { label: "1BU - Mfg & Trade Inventories", href: "nipa/1bu.html" },
      { label: "2.4.4U - PCE Deflator", href: "nipa/2_4_4u.html" },
      { label: "2.4.5U - Nominal Spending", href: "nipa/2_4_5u.html" },
      { label: "2.4.6U - Real Spending", href: "nipa/2_4_6u.html" },
      { label: "2BU - Mfg & Trade Sales", href: "nipa/2bu.html" },
      { label: "3BU - Inventory-Sales Ratio", href: "nipa/3bu.html" },
      { label: "4.2.5B - Net Exports", href: "nipa/4_2_5b.html" },
      { label: "4.2.6B - Real Imports", href: "nipa/4_2_6b.html" },
      { label: "5.5.5U - Equipment Spending", href: "nipa/5_5_5u.html" },
      { label: "5.7.5BU1 - Private Inventories", href: "nipa/5_7_5bu1.html" },
    ]
  },
  { label: "M3 - Shipments, Inventories & Orders", href: "m3/index.html" },
  {
    label: "Current Employment Statistics", children: [
      { label: "Employees YoY", href: "ces/employees_yoy.html" },
      { label: "Employees (Long)", href: "ces/employees_long.html" },
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
    ]
  },
  { label: "Unemployment by Industry", href: "unemployment/index.html" },
  { label: "Industrial Production", href: "industrial_production/index.html" },
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
    // src is like "../js/nav.js" or "./js/nav.js" or "js/nav.js"
    // Strip off "js/nav.js" to get the path to site root
    siteRoot = src.replace(/js\/nav\.js$/, '');
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
  html += '<div class="nav-header"><h1><a href="' + resolvePath('index.html') + '">NewCo Charts</a></h1></div>';

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
