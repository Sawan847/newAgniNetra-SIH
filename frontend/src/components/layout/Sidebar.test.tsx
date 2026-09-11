import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LanguageProvider } from "../../i18n/LanguageContext";
import { Sidebar } from "./Sidebar";

describe("Sidebar Component", () => {
  it("renders all command centre navigation links", () => {
    render(
      <LanguageProvider><MemoryRouter>
        <Sidebar collapsed={false} onToggle={() => {}} />
      </MemoryRouter></LanguageProvider>
    );

    expect(screen.getByText("AgniNetra AI")).toBeInTheDocument();
    const links = screen.getAllByRole("link");
    expect(links.map(link => link.getAttribute("href"))).toEqual([
      "/", "/investigate", "/facilities", "/analytics", "/alerts", "/model", "/labelling", "/system",
    ]);
    expect(screen.getByText("Live Command Centre")).toBeInTheDocument();

  });

  it("hides labels when collapsed", () => {
    render(
      <LanguageProvider><MemoryRouter>
        <Sidebar collapsed={true} onToggle={() => {}} />
      </MemoryRouter></LanguageProvider>
    );

    expect(screen.queryByText("Live Command Centre")).not.toBeInTheDocument();
    expect(screen.queryByText("Alerts Centre")).not.toBeInTheDocument();
  });
});
