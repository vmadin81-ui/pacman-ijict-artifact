export default [
  {
    files: ["*.js", "**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: { window: "readonly", document: "readonly", requestAnimationFrame: "readonly", cancelAnimationFrame: "readonly", console: "readonly" },
    },
    rules: { "no-undef": "error", "no-unused-vars": "warn", "no-unreachable": "error", "no-dupe-keys": "error", "no-redeclare": "error", eqeqeq: "warn" },
  },
];
