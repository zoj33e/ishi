// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Board } from "@/components/board/Board";
import en from "../messages/en.json";

afterEach(cleanup);

function setup(props: Partial<React.ComponentProps<typeof Board>> = {}) {
  const onPlay = vi.fn();
  render(
    <NextIntlClientProvider locale="en" messages={en}>
      <Board size={9} stones={{ black: ["C3"], white: [] }} toMove="white" lastMove="C3" onPlay={onPlay} {...props} />
    </NextIntlClientProvider>,
  );
  const cell = (p: string) => document.querySelector(`rect[data-point="${p}"]`)!;
  const ghost = () => screen.queryByTestId("ghost");
  return { onPlay, cell, ghost };
}

// jsdom has no PointerEvent constructor; build one RTL can dispatch with a pointerType.
function pointer(type: "pointerUp" | "pointerMove", el: Element, pointerType: string) {
  const ev = new MouseEvent(type === "pointerUp" ? "pointerup" : "pointermove", { bubbles: true });
  Object.defineProperty(ev, "pointerType", { value: pointerType });
  fireEvent(el, ev);
}

describe("Board input", () => {
  it("touch: first tap places a ghost, second tap on the same point confirms", () => {
    const { onPlay, cell, ghost } = setup();
    pointer("pointerUp", cell("E5"), "touch");
    expect(ghost()?.getAttribute("data-point")).toBe("E5");
    expect(onPlay).not.toHaveBeenCalled();
    pointer("pointerUp", cell("E5"), "touch");
    expect(onPlay).toHaveBeenCalledWith("E5");
    expect(ghost()).toBeNull();
  });

  it("touch: tapping a different point moves the ghost instead of playing", () => {
    const { onPlay, cell, ghost } = setup();
    pointer("pointerUp", cell("E5"), "touch");
    pointer("pointerUp", cell("D4"), "touch");
    expect(ghost()?.getAttribute("data-point")).toBe("D4");
    expect(onPlay).not.toHaveBeenCalled();
  });

  it("mouse: hover shows the ghost and one click plays", () => {
    const { onPlay, cell, ghost } = setup();
    pointer("pointerMove", cell("F6"), "mouse");
    expect(ghost()?.getAttribute("data-point")).toBe("F6");
    pointer("pointerUp", cell("F6"), "mouse");
    expect(onPlay).toHaveBeenCalledWith("F6");
  });

  it("ignores occupied points and read-only boards", () => {
    const { onPlay, cell, ghost } = setup();
    pointer("pointerUp", cell("C3"), "touch");
    pointer("pointerUp", cell("C3"), "mouse");
    expect(ghost()).toBeNull();
    expect(onPlay).not.toHaveBeenCalled();
    cleanup();
    const ro = setup({ interactive: false });
    pointer("pointerUp", ro.cell("E5"), "touch");
    pointer("pointerUp", ro.cell("E5"), "touch");
    expect(ro.onPlay).not.toHaveBeenCalled();
  });

  it("keyboard: arrows move focus, Enter twice plays", () => {
    const { onPlay, cell } = setup();
    const start = cell("E5") as SVGRectElement;
    expect(start.getAttribute("tabindex")).toBe("0");
    fireEvent.keyDown(start, { key: "ArrowUp" });
    expect(cell("E6").getAttribute("tabindex")).toBe("0");
    fireEvent.keyDown(cell("E6"), { key: "Enter" });
    fireEvent.keyDown(cell("E6"), { key: "Enter" });
    expect(onPlay).toHaveBeenCalledWith("E6");
  });

  it("labels every intersection for screen readers", () => {
    const { cell } = setup();
    expect(document.querySelectorAll('rect[role="gridcell"]')).toHaveLength(81);
    expect(cell("C3").getAttribute("aria-label")).toBe("C3, black stone");
    expect(cell("E5").getAttribute("aria-label")).toBe("E5, empty");
    expect(screen.getByTestId("last-move")).toBeTruthy();
  });
});

describe("Board select mode", () => {
  it("one tap selects any point, stones included, without a ghost", () => {
    const onSelect = vi.fn();
    render(
      <NextIntlClientProvider locale="en" messages={en}>
        <Board size={5} stones={{ black: ["C3"], white: [] }} onSelect={onSelect} />
      </NextIntlClientProvider>,
    );
    const cell = (p: string) => document.querySelector(`rect[data-point="${p}"]`)!;
    pointer("pointerUp", cell("C3"), "touch");
    pointer("pointerUp", cell("A1"), "mouse");
    expect(onSelect.mock.calls).toEqual([["C3"], ["A1"]]);
    expect(document.querySelector('[data-testid="ghost"]')).toBeNull();
  });
});

describe("Board lesson extras", () => {
  it("draws the learner's move faded, but not over a real stone", () => {
    setup({ faded: [{ point: "F8", color: "black" }, { point: "C3", color: "black" }] });
    const faded = screen.getAllByTestId("faded");
    expect(faded.map((f) => f.getAttribute("data-point"))).toEqual(["F8"]);
    expect(faded[0].getAttribute("opacity")).toBe("0.45");
  });

  it("highlights a 3x3 area around the hint point, clipped at the edge", () => {
    setup({ highlight: "E5" });
    const mid = screen.getByTestId("highlight");
    cleanup();
    setup({ highlight: "A1" });
    const corner = screen.getByTestId("highlight");
    expect(Number(corner.getAttribute("width"))).toBeCloseTo((Number(mid.getAttribute("width")) * 2) / 3);
    expect(Number(corner.getAttribute("height"))).toBeCloseTo((Number(mid.getAttribute("height")) * 2) / 3);
  });

  it("draws no highlight without a hint point", () => {
    setup();
    expect(screen.queryByTestId("highlight")).toBeNull();
  });
});
