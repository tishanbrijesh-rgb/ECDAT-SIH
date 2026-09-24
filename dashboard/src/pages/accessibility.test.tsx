// Accessibility unit tests for Stage 11 repair verification.
// Covers: form labels, heading order, ARIA roles, error announcements,
// dialogs, focus trapping, theme toggle, scan form, and login form semantics.
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Login from "../pages/Login";
import { ApiError, login } from "../api/client";
import ScanPage from "../pages/ScanPage";
import { ConfirmDialog } from "../components/ConfirmDialog";
import ThemeToggle from "../components/ThemeToggle";

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  login: vi.fn(),
}));

const mockedLogin = vi.mocked(login);

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Login ──────────────────────────────────────────────────────────────

describe("Login accessibility", () => {
  it("provides a skip link to the login main content", () => {
    render(<Login onSuccess={vi.fn()} />);

    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
  });

  it("exposes username and password fields with accessible labels", () => {
    render(<Login onSuccess={vi.fn()} />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("announces authentication errors via alert role", async () => {
    mockedLogin.mockRejectedValueOnce(new ApiError("Unauthorized", 401));
    render(<Login onSuccess={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid username or password.");
  });

  it("displays session-expiry message and marks fields invalid", () => {
    render(<Login onSuccess={vi.fn()} message="Your session expired. Please sign in again." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Your session expired");
    expect(screen.getByLabelText("Username")).toHaveAttribute("aria-invalid", "true");
  });

  it("has a single h1 for the page heading", () => {
    const { container } = render(<Login onSuccess={vi.fn()} />);
    const h1s = container.querySelectorAll("h1");
    expect(h1s.length).toBe(1);
    expect(h1s[0]).toHaveTextContent("Sign in");
  });
});

// ── ConfirmDialog ──────────────────────────────────────────────────────

describe("ConfirmDialog accessibility", () => {
  it("renders with alertdialog semantics", () => {
    render(
      <ConfirmDialog
        open
        title="Confirm action"
        message="Are you sure?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby");
    expect(dialog).toHaveAttribute("aria-describedby");
    expect(screen.getByRole("heading", { name: "Confirm action" })).toBeInTheDocument();
  });

  it("focuses the cancel button on open", async () => {
    render(
      <ConfirmDialog open title="Test" message="Message" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("closes on Escape key", async () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="Test" message="x" onConfirm={vi.fn()} onCancel={onCancel} />);
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalled();
  });

  it("traps focus within the dialog via Tab key", async () => {
    render(
      <ConfirmDialog open title="Focus trap" message="x" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Confirm" });
    await act(async () => {
      await new Promise((resolve) => requestAnimationFrame(() => resolve(undefined)));
    });
    // Focus starts on Cancel after the dialog's scheduled focus runs.
    expect(cancel).toHaveFocus();
    // Tab from the last focusable element (Confirm) wraps to the first (Cancel)
    confirm.focus();
    await userEvent.keyboard("{Tab}");
    expect(cancel).toHaveFocus();
  });
});

// ── ThemeToggle ────────────────────────────────────────────────────────

describe("ThemeToggle accessibility", () => {
  it("has an accessible name describing its action", () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-label");
    expect(btn.getAttribute("aria-label")).toMatch(/switch to .+ mode/i);
  });

  it("is a button that can receive keyboard focus", async () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("button");
    btn.focus();
    expect(btn).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    // After cycling, the button should still be focusable
    expect(screen.getByRole("button")).toBeInTheDocument();
  });
});

// ── ScanPage form ──────────────────────────────────────────────────────

describe("ScanPage form accessibility", () => {
  it("exposes the repository path input with an accessible label", () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<ScanPage />} />
        </Routes>
      </MemoryRouter>,
    );
    const input = screen.getByRole("textbox", { name: /repository path/i });
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "false");
  });

  it("exposes error state with aria-invalid and describes the error", async () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<ScanPage />} />
        </Routes>
      </MemoryRouter>,
    );
    const input = screen.getByRole("textbox", { name: /repository path/i });
    await userEvent.type(input, "bad");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "scan-path-error");
  });

  it("links the heading to the input group via aria-labelledby", () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<ScanPage />} />
        </Routes>
      </MemoryRouter>,
    );
    const heading = screen.getByRole("heading", { name: "Repository path" });
    const group = heading.closest('[role="group"]');
    expect(group).toHaveAttribute("aria-labelledby", "scan-repo-heading");
  });
});
