import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./Login";
import { login } from "../api/client";

vi.mock("../api/client", () => ({ login: vi.fn() }));

const mockedLogin = vi.mocked(login);

describe("Login", () => {
  beforeEach(() => mockedLogin.mockReset());

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
