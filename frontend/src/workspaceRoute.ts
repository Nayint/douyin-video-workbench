const pages = new Set([
  "home",
  "world",
  "collected",
  "library",
  "products",
  "create",
  "drafts",
  "tasks",
  "settings",
]);
export function workspaceRoute(hash: string) {
  const [page, id] = hash.replace(/^#\/?/, "").split("/");
  return {
    page: pages.has(page) ? page : "home",
    selected:
      ["library", "collected"].includes(page) &&
      /^[0-9a-f-]{36}$/i.test(id || "")
        ? id
        : null,
  };
}
export function workspaceHash(page: string, selected: string | null) {
  return "#/" + page + (selected ? "/" + selected : "");
}
