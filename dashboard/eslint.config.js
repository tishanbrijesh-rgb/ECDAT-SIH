import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

export default [
    {
        files: ["src/**/*.{ts,tsx}"],
        languageOptions: {
            parser: tsParser,
            parserOptions: {
                ecmaVersion: 2020,
                sourceType: "module",
                ecmaFeatures: { jsx: true },
                project: "./tsconfig.json",
            },
        },
        plugins: {
            "@typescript-eslint": tsPlugin,
        },
        rules: {
            ...tsPlugin.configs.recommended.rules,
            // The base rule does not understand TypeScript type positions and
            // duplicates every useful diagnostic from the TS-aware rule.
            "no-unused-vars": "off",
            "@typescript-eslint/no-explicit-any": "warn",
            "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
        },
    },
];
