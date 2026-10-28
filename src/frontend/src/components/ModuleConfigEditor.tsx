import { useState } from "react";
import type { Config, ConfigOverrides, ModuleSchema, Registry, SettingSchema } from "../types";
import { mergeConfig } from "../config";
import { Seg, Switch, Tag } from "../ui";

const MODULE_ICONS: Record<string, string> = {
  on_demand_feedback: "💬", realtime_feedback: "⚡", feedback_presentation: "🎭", student_rating: "👍",
  instructor_review: "🧑‍🏫", reward: "🎯", learner_model: "🧠", questionnaire: "📋", get_started: "🚀",
  version_history: "🕘", paste_control: "📋", submission_rules: "📏", grades: "🎓",
};

export function moduleIcon(key: string) {
  return MODULE_ICONS[key] ?? "🧩";
}

/**
 * Schema-driven editor for ONE configuration layer. `value` holds only this layer's overrides;
 * `inherited` is the resolved config from all layers beneath it. Every module and setting
 * can be left to inherit, or overridden here — that's what makes each component A/B-testable.
 */
export function ModuleConfigEditor({
  registry, value, inherited, onChange, inheritLabel, filter, readOnly,
}: {
  registry: Registry;
  value: ConfigOverrides;
  inherited: Config;
  onChange: (next: ConfigOverrides) => void;
  inheritLabel: string;
  filter?: (m: ModuleSchema) => boolean;
  readOnly?: boolean;
}) {
  const effective = mergeConfig(inherited, value);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const mods = registry.modules.filter(filter ?? (() => true));
  const cats = [...new Set(mods.map((m) => m.category))];

  const set = (mod: string, field: string, v: unknown) => {
    const next = { ...value, [mod]: { ...(value[mod] ?? {}), [field]: v } };
    onChange(next);
  };
  const unset = (mod: string, field: string) => {
    const m = { ...(value[mod] ?? {}) };
    delete m[field];
    const next = { ...value };
    if (Object.keys(m).length) next[mod] = m;
    else delete next[mod];
    onChange(next);
  };

  return (
    <div>
      {cats.map((cat) => (
        <div key={cat}>
          <div className="mod-cat">{cat}</div>
          {mods.filter((m) => m.category === cat).map((m) => {
            const own = value[m.key] ?? {};
            const enabledOverride = own.enabled;
            const blockedBy = m.depends_on.filter((d) => !effective[d]?.enabled);
            const isOn = effective[m.key].enabled && blockedBy.length === 0;
            const nOwn = Object.keys(own).filter((k) => k !== "enabled").length;
            const isOpen = open[m.key] ?? false;
            return (
              <div className="mod" key={m.key}>
                <div className="mod-head">
                  <span
                    className={`caret ${isOpen ? "open" : ""}`} style={{ cursor: "pointer" }}
                    onClick={() => setOpen({ ...open, [m.key]: !isOpen })}
                  >▶</span>
                  <span style={{ fontSize: 16 }}>{moduleIcon(m.key)}</span>
                  <div style={{ flex: 1, minWidth: 0, cursor: "pointer" }} onClick={() => setOpen({ ...open, [m.key]: !isOpen })}>
                    <div className="row" style={{ gap: 6 }}>
                      <span className="mod-title">{m.label}</span>
                      {m.srs_refs.length > 0 && <span className="ref">{m.srs_refs.join(" · ")}</span>}
                      {nOwn > 0 && <Tag color="blue">{nOwn} setting{nOwn > 1 ? "s" : ""} changed</Tag>}
                      {blockedBy.length > 0 && <Tag color="orange">needs {blockedBy.join(", ")}</Tag>}
                    </div>
                    <div className="mod-desc">{m.description}</div>
                  </div>
                  {readOnly ? (
                    <Tag color={isOn ? "green" : "gray"} dot>{isOn ? "On" : "Off"}</Tag>
                  ) : (
                    <div className="row" style={{ gap: 8 }}>
                      <Seg
                        value={enabledOverride === undefined ? "inherit" : enabledOverride ? "on" : "off"}
                        options={[
                          { value: "inherit", label: `Inherit (${inherited[m.key].enabled ? "on" : "off"})` },
                          { value: "on", label: "On" },
                          { value: "off", label: "Off" },
                        ]}
                        onChange={(v) => (v === "inherit" ? unset(m.key, "enabled") : set(m.key, "enabled", v === "on"))}
                      />
                    </div>
                  )}
                </div>
                {isOpen && (
                  <div className="mod-body">
                    {m.settings.length === 0 && <div className="faint small">No settings — this module is a pure on/off switch.</div>}
                    {m.settings.map((s) => (
                      <SettingRow
                        key={s.key} s={s} registry={registry} readOnly={readOnly}
                        value={effective[m.key][s.key]} overridden={s.key in own}
                        inheritedValue={inherited[m.key][s.key]} inheritLabel={inheritLabel}
                        onChange={(v) => set(m.key, s.key, v)} onReset={() => unset(m.key, s.key)}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function fmt(v: unknown): string {
  if (Array.isArray(v)) return v.length ? v.join(", ") : "all";
  if (typeof v === "boolean") return v ? "on" : "off";
  return String(v);
}

function SettingRow({ s, value, overridden, inheritedValue, inheritLabel, onChange, onReset, registry, readOnly }: {
  s: SettingSchema; value: unknown; overridden: boolean; inheritedValue: unknown; inheritLabel: string;
  onChange: (v: unknown) => void; onReset: () => void; registry: Registry; readOnly?: boolean;
}) {
  const options = s.options_source === "styles" ? registry.styles.map((x) => x.key) : s.options ?? [];
  let ctrl;
  if (s.type === "bool") {
    ctrl = <Switch on={!!value} onChange={onChange} disabled={readOnly} />;
  } else if (s.type === "enum") {
    ctrl = (
      <select className="select" value={String(value)} disabled={readOnly} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o} value={o}>{o.replace(/_/g, " ")}</option>)}
      </select>
    );
  } else if (s.type === "multi_enum") {
    const cur = (value as string[]) ?? [];
    ctrl = (
      <div className="row wrap" style={{ gap: 4 }}>
        {options.map((o) => {
          const on = cur.includes(o);
          return (
            <button
              key={o} type="button" disabled={readOnly} className="btn sm outline"
              style={on ? { background: "var(--blue-bg)", color: "var(--blue)" } : undefined}
              onClick={() => onChange(on ? cur.filter((x) => x !== o) : [...cur, o])}
            >{on ? "✓ " : ""}{o.replace(/_/g, " ")}</button>
          );
        })}
        {cur.length === 0 && <span className="faint small">none selected = all enabled styles</span>}
      </div>
    );
  } else if (s.type === "text") {
    ctrl = <textarea className="textarea" value={String(value ?? "")} disabled={readOnly} onChange={(e) => onChange(e.target.value)} />;
  } else {
    ctrl = (
      <input
        className="input" type="number" disabled={readOnly} value={String(value)}
        min={s.min ?? undefined} max={s.max ?? undefined} step={s.type === "float" ? 0.05 : 1}
        onChange={(e) => e.target.value !== "" && onChange(s.type === "int" ? parseInt(e.target.value) : parseFloat(e.target.value))}
      />
    );
  }
  return (
    <div className="set-row" title={s.help}>
      <div className="set-label">
        {s.label}
        {s.help && <div className="faint" style={{ fontSize: 11.5, lineHeight: 1.3 }}>{s.help}</div>}
      </div>
      <div className="set-ctrl">
        {ctrl}
        {overridden ? (
          <>
            <span className="prov here">● set here</span>
            {!readOnly && <button className="reset" onClick={onReset}>reset to {fmt(inheritedValue)}</button>}
          </>
        ) : (
          <span className="prov">from {inheritLabel}</span>
        )}
      </div>
    </div>
  );
}

/** Compact read-only summary of an override layer, e.g. for experiment condition cards. */
export function OverrideSummary({ registry, config }: { registry: Registry; config: ConfigOverrides }) {
  const entries = Object.entries(config);
  if (!entries.length) return <span className="faint small">No changes — baseline configuration</span>;
  return (
    <div className="row wrap" style={{ gap: 4 }}>
      {entries.flatMap(([mod, vals]) => {
        const m = registry.modules.find((x) => x.key === mod);
        return Object.entries(vals).map(([k, v]) => {
          const label = k === "enabled" ? "" : ` · ${m?.settings.find((s) => s.key === k)?.label ?? k}: ${fmt(v)}`;
          const color = k === "enabled" ? (v ? "green" : "red") : "gray";
          return (
            <Tag key={mod + k} color={color as "green"}>
              {moduleIcon(mod)} {m?.label ?? mod}{k === "enabled" ? (v ? " on" : " off") : label}
            </Tag>
          );
        });
      })}
    </div>
  );
}
