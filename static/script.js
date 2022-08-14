import "https://cdn.skypack.dev/@hotwired/turbo";

function parseValue(formattedValue) {
  // Handle numbers only.
  if (/^\d+$/.test(formattedValue)) {
    const parsedValue = parseInt(formattedValue, 10);
    if (!isNaN(parsedValue)) {
      return parsedValue;
    }
  }

  let parsedValue = 0;

  // Handle numbers with units.
  const matches = formattedValue.matchAll(
    /-?(\d+)\s*(:|h|horas?|m|minutos?|)\s*/gi
  );
  for (const match of matches) {
    const [, value, unit] = match;
    if (unit.toLowerCase().startsWith("h") || unit === ":") {
      parsedValue += parseInt(value, 10) * 60;
    } else {
      parsedValue += parseInt(value, 10);
    }
  }
  return formattedValue.startsWith("-") ? parsedValue * -1 : parsedValue;
}

function formatValue(value) {
  const parsedValue = parseInt(value, 10);

  if (isNaN(parsedValue)) {
    return "";
  }

  const h = Math.floor(Math.abs(parsedValue) / 60);
  const m = Math.abs(parsedValue) % 60;

  const parts = [];

  if (h > 0) {
    parts.push(`${h} hora${h !== 1 ? "s" : ""}`);
  }
  if (m > 0) {
    parts.push(`${m} minuto${m !== 1 ? "s" : ""}`);
  }

  // return (parsedValue < 0 ? "-" : "") + parts.join(" ");
  return parts.join(" ");
}

class EntryForm extends HTMLElement {
  value = 0;

  connectedCallback() {
    this.valueInput = this.querySelector('input[slot="value-input"]');
    this.formattedValueInput = this.querySelector(
      'input[slot="formatted-value-input"]'
    );

    this.flipValueOptionGroup = this.querySelector(
      '[slot="flip-value-option-group"]'
    );

    this.addTimeButtonGroup = this.querySelector(
      '[slot="add-time-button-group"]'
    );

    this.flipValueOptionGroup.addEventListener("change", (e) => {
      if (!e.target.checked) {
        return;
      }
      if (e.target.value === "+") {
        this.value = Math.abs(this.value);
      } else if (e.target.value === "-") {
        this.value *= -1;
      }
      this.updateInputs();
    });

    this.addTimeButtonGroup.addEventListener("click", (e) => {
      if (e.target.tagName !== "BUTTON") {
        return;
      }
      const addedValue = parseInt(e.target.value, 10);
      if (isNaN(addedValue)) {
        return;
      }
      this.value += addedValue * (this.value < 0 ? -1 : 1);
      this.updateInputs();
    });

    this.valueInput.addEventListener("change", (e) => {
      const parsedValue = parseInt(e.target.value, 10);
      if (isNaN(parsedValue)) {
        return;
      }
      this.value = parseValue;
      this.updateFormattedValueInput();
    });

    this.formattedValueInput.addEventListener("input", (e) => {
      this.value = parseValue(e.target.value);
      this.updateValueInput();
    });

    this.formattedValueInput.pattern =
      "^-?(\\d+|(\\d+\\s*(:|h|horas?|m|minutos?|)\\s*)+)$";
  }

  updateValueInput() {
    this.valueInput.value = String(this.value);
  }

  updateFormattedValueInput() {
    this.formattedValueInput.value = formatValue(this.value);

    if (this.value >= 0) {
      this.flipValueOptionGroup.querySelector(
        'input[value="+"]'
      ).checked = true;
    } else {
      this.flipValueOptionGroup.querySelector(
        'input[value="-"]'
      ).checked = true;
    }
  }

  updateInputs() {
    this.updateValueInput();
    this.updateFormattedValueInput();
  }
}

if (!window.customElements.get("entry-form")) {
  window.EntryForm = EntryForm;
  window.customElements.define("entry-form", EntryForm);
}
