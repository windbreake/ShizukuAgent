export const modelLabel = (model: Record<string, unknown>) => {
  const name = String(model.name || '').trim();
  return !name || /^(primary agent model|primary model|agent model|default model)$/i.test(name)
    ? String(model.model || model.id || '') : name;
};
