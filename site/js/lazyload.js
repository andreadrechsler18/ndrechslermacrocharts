/* NewCo Charts - Lazy Loading via IntersectionObserver */

window.NewCoLazyLoad = {
  observer: null,
  renderQueue: [],
  rendering: false,
  BATCH_SIZE: 8,

  init(renderCallback) {
    this.renderCallback = renderCallback;

    this.observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        const idx = parseInt(entry.target.dataset.seriesIndex, 10);

        if (entry.isIntersecting) {
          // Queue for rendering
          if (!this.renderQueue.includes(idx)) {
            this.renderQueue.push(idx);
          }
          this.observer.unobserve(entry.target);
        }
      });

      if (this.renderQueue.length > 0 && !this.rendering) {
        this.processBatch();
      }
    }, {
      rootMargin: '600px 0px',
      threshold: 0
    });
  },

  observe(element) {
    this.observer.observe(element);
  },

  async processBatch() {
    if (this.renderQueue.length === 0) {
      this.rendering = false;
      return;
    }

    this.rendering = true;
    const batch = this.renderQueue.splice(0, this.BATCH_SIZE);
    console.log('[NewCo] processBatch: rendering indices', batch);

    for (const idx of batch) {
      try {
        await this.renderCallback(idx);
      } catch (e) {
        console.error('Chart render failed for index', idx, e);
      }
    }

    if (this.renderQueue.length > 0) {
      requestAnimationFrame(() => this.processBatch());
    } else {
      this.rendering = false;
    }
  }
};
