import "https://cdn.skypack.dev/@hotwired/turbo";

const supportedUnits = [
  {
    pattern: "(([+-]?)\\d+(,\\d+)?)(:|horas|hora|h)",
    parse: (match) => Math.round(parseFloat(match[1].replace(",", ".")) * 60),
  },
  {
    pattern: "(([+-]?)\\d+)(minutos|minuto|min|m|$)",
    parse: (match) => parseInt(match[1], 10),
  },
];

function parseValue(formattedValue) {
  const normalizedValue = formattedValue.toLowerCase().replace(/\s+/g, "");

  // Handle numbers only.
  if (/^[+-]?\d+$/g.test(normalizedValue)) {
    const parsedValue = parseInt(normalizedValue, 10);
    if (!isNaN(parsedValue)) {
      return parsedValue;
    }
  }

  let parsedValue = 0;

  supportedUnits.forEach((unit) => {
    const matches = normalizedValue.matchAll(new RegExp(unit.pattern, "g"));
    for (const match of matches) {
      parsedValue += unit.parse(match);
    }
  });

  return parsedValue;
}

function formatValue(value) {
  const parsedValue = parseInt(value, 10);

  if (isNaN(parsedValue)) {
    return "";
  }

  const absoluteValue = Math.abs(parsedValue);

  const h = Math.floor(absoluteValue / 60);
  const m = absoluteValue % 60;

  const parts = [];

  if (h > 0) {
    parts.push(`${h} hora${h !== 1 ? "s" : ""}`);
  }
  if (m > 0) {
    parts.push(`${m} minuto${m !== 1 ? "s" : ""}`);
  }

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
      this.value = parsedValue;
      this.updateInputs();
    });

    this.formattedValueInput.addEventListener("change", (e) => {
      this.value = parseValue(e.target.value);
      this.updateInputs();
    });

    this.formattedValueInput.pattern = "^(\\d+ (horas?|minutos?)(\\s|$))+";
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
