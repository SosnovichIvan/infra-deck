import { defineConfig } from "cypress";
export default defineConfig({
  allowCypressEnv: false,
  defaultCommandTimeout: 20000,
  video: false,
  screenshotOnRunFailure: true,
  e2e: { baseUrl: "http://localhost:5187", supportFile: false },
  viewportWidth: 1440,
  viewportHeight: 1000,
});
