import { render } from "preact";
import { App } from "src/components/App";

const root = document.getElementById("root");

if (root) {
  render(<App />, root);
}
