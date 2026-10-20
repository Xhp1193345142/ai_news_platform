<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({ block: { type: Object, required: true } });
const selectedIndex = ref(0);
const chartTarget = ref(null);
const renderError = ref("");
let embeddedView = null;

const OPENAI_THEME_COLORS = {
  theme1_blue: "#e6f0ff",
  theme3_blue: "#a9c8ff",
  theme4_blue: "#5278c5",
  theme2_pink: "#efb5cc",
  theme1_orange: "#ff9a68",
  theme3_orange: "#ffc0a6",
  theme2_green: "#a7d56c",
};

function resolveThemeColors(value) {
  if (Array.isArray(value)) return value.map(resolveThemeColors);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, resolveThemeColors(entry)]));
  }
  return typeof value === "string" ? (OPENAI_THEME_COLORS[value] ?? value) : value;
}

function themedSpec(spec) {
  // Article data is reactive after it enters Vue. Vega uses structuredClone
  // internally, which cannot clone Vue Proxy objects, so remove all proxies
  // before handing the specification to vega-embed.
  const plainSpec = resolveThemeColors(JSON.parse(JSON.stringify(spec)));
  return {
    ...plainSpec,
    width: "container",
    height: 420,
    autosize: { type: "fit", contains: "padding", resize: true },
    background: "transparent",
    config: {
      ...(plainSpec.config ?? {}),
      axis: {
        labelColor: "#f4f7ff",
        titleColor: "#f4f7ff",
        domainColor: "#d7e3f7",
        tickColor: "#d7e3f7",
        gridColor: "rgba(190, 209, 235, 0.16)",
        ...(plainSpec.config?.axis ?? {}),
      },
      legend: {
        labelColor: "#f4f7ff",
        titleColor: "#f4f7ff",
        ...(plainSpec.config?.legend ?? {}),
      },
      title: {
        color: "#f4f7ff",
        subtitleColor: "#9caccb",
        ...(plainSpec.config?.title ?? {}),
      },
      view: { stroke: "transparent", ...(plainSpec.config?.view ?? {}) },
    },
  };
}

async function renderChart() {
  await nextTick();
  if (!chartTarget.value) return;
  embeddedView?.finalize();
  embeddedView = null;
  renderError.value = "";
  const item = props.block.data.items[selectedIndex.value];
  try {
    const { default: vegaEmbed } = await import("vega-embed");
    const result = await vegaEmbed(chartTarget.value, themedSpec(item.spec), {
      actions: false,
      renderer: "svg",
    });
    embeddedView = result.view;
  } catch (error) {
    renderError.value = error instanceof Error ? error.message : "图表加载失败";
  }
}

function selectChart(index) {
  selectedIndex.value = index;
}

watch(selectedIndex, renderChart);
onMounted(renderChart);
onBeforeUnmount(() => embeddedView?.finalize());
</script>

<template>
  <section class="reader-chart-tabs">
    <div class="chart-tab-list" role="tablist" aria-label="评测图表">
      <button
        v-for="(item, index) in block.data.items"
        :id="`${block.id}-chart-tab-${index}`"
        :key="item.label"
        type="button"
        role="tab"
        :aria-selected="selectedIndex === index"
        :aria-controls="`${block.id}-chart-panel`"
        :class="{ active: selectedIndex === index }"
        @click="selectChart(index)"
      >{{ item.label }}</button>
    </div>
    <div
      :id="`${block.id}-chart-panel`"
      class="chart-tab-panel"
      role="tabpanel"
      :aria-labelledby="`${block.id}-chart-tab-${selectedIndex}`"
    >
      <div ref="chartTarget" class="vega-chart" />
      <p v-if="renderError" class="chart-render-error">{{ renderError }}</p>
    </div>
  </section>
</template>
