const MIRROR_PROPS: Array<keyof CSSStyleDeclaration> = [
  "boxSizing",
  "width",
  "borderTopWidth",
  "borderRightWidth",
  "borderBottomWidth",
  "borderLeftWidth",
  "borderStyle",
  "paddingTop",
  "paddingRight",
  "paddingBottom",
  "paddingLeft",
  "fontStyle",
  "fontVariant",
  "fontWeight",
  "fontStretch",
  "fontSize",
  "lineHeight",
  "fontFamily",
  "textAlign",
  "textTransform",
  "textIndent",
  "letterSpacing",
  "wordSpacing",
  "tabSize",
  "wordBreak",
];

export interface CaretCoords {
  top: number;
  left: number;
  height: number;
}

/**
 * Measures where a given character offset inside a <textarea> renders on
 * screen, via the classic hidden-mirror-div trick (textareas expose no
 * native API for this, unlike contentEditable's Range.getBoundingClientRect).
 */
export function getCaretCoordinates(
  element: HTMLTextAreaElement,
  position: number,
): CaretCoords {
  const div = document.createElement("div");
  document.body.appendChild(div);
  const style = div.style;
  const computed = window.getComputedStyle(element);

  style.position = "absolute";
  style.visibility = "hidden";
  style.whiteSpace = "pre-wrap";
  style.wordWrap = "break-word";
  style.top = "0";
  style.left = "0";

  MIRROR_PROPS.forEach((prop) => {
    const value = computed[prop];
    if (typeof value === "string") {
      (style as unknown as Record<string, string>)[prop as string] = value;
    }
  });
  style.width = computed.width;

  div.textContent = element.value.substring(0, position);
  const span = document.createElement("span");
  span.textContent = element.value.substring(position) || ".";
  div.appendChild(span);

  const rect = element.getBoundingClientRect();
  const lineHeight = parseFloat(computed.lineHeight || "20") || 20;

  const coords: CaretCoords = {
    top: rect.top + span.offsetTop - element.scrollTop,
    left: rect.left + span.offsetLeft - element.scrollLeft,
    height: lineHeight,
  };

  document.body.removeChild(div);
  return coords;
}
