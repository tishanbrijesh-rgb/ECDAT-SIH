import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./Login";
import { ApiError, login } from "../api/client";

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  login: vi.fn(),
}));

const mockedLogin = vi.mocked(login);

describe("Login", () => {
  beforeEach(() => {
    mockedLogin.mockReset();
  });

  it("renders the recovered ECDAT brand asset", () => {
    const { container } = render(<Login onSuccess={vi.fn()} />);

    expect(container.querySelector('img.brand-mark[src="/ecdat-logo.svg"]')).toBeInTheDocument();
  });

  it.each([
    [new ApiError("Unauthorized", 401), "Invalid username or password."],
    [new ApiError("Rate limited", 429), "Too many sign-in attempts. Please try again later."],
    [new TypeError("Failed to fetch"), "Unable to sign in. Check your connection and try again."],
  ])("reports the appropriate sign-in failure", async (error, message) => {
    mockedLogin.mockRejectedValue(error);
    render(<Login onSuccess={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("submits the entered credentials and completes a successful sign-in", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    mockedLogin.mockResolvedValue(undefined);
    render(<Login onSuccess={onSuccess} />);

    const submit = screen.getByRole("button", { name: "Sign in" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("Username"), "security-user");
    await user.type(screen.getByLabelText("Password"), "correct horse battery staple");
    await user.click(submit);

    expect(mockedLogin).toHaveBeenCalledWith("security-user", "correct horse battery staple");
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("exposes a session-expiry message and marks the fields invalid", () => {
    const onSuccess = vi.fn();
    render(<Login onSuccess={onSuccess} message="Your session expired. Please sign in again." />);

    expect(screen.getByRole("alert")).toHaveTextContent("Your session expired");
    expect(screen.getByLabelText("Username")).toHaveAttribute("aria-invalid", "true");
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
