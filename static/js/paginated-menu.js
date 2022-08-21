class PaginatedMenu extends HTMLElement {
  selectedPage = null;

  connectedCallback() {
    this.addEventListener("click", (event) => {
      const page = event.target.getAttribute("data-change-page");
      if (page) {
        this.setSelectedPage(page);
      }
    });

    this.selectedPage = this.getAttribute("data-selected-page");
    this.refresh();
  }

  setSelectedPage(page) {
    this.selectedPage = page;
    this.refresh();
  }

  refresh() {
    this.querySelectorAll(`[data-page]`).forEach((element) => {
      if (element.dataset.page === this.selectedPage) {
        element.removeAttribute("hidden");
      } else {
        element.setAttribute("hidden", "");
      }
    });
  }
}

if (!window.customElements.get("paginated-menu")) {
  window.PaginatedMenu = PaginatedMenu;
  window.customElements.define("paginated-menu", PaginatedMenu);
}
