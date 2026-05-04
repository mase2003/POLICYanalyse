<!-- 纯前端轮播；数据来自 dashboard.carousel -->
<template>
  <div class="carousel">
    <div v-if="normalizedSlides.length" class="track" :style="{ transform: `translateX(-${index * 100}%)` }">
      <div v-for="(s, i) in normalizedSlides" :key="i" class="slide">
        <img class="slide-image" :src="s.imageUrl" :alt="s.title || `轮播图${i + 1}`" />
      </div>
    </div>
    <div v-else class="empty">暂无轮播图</div>
    <div v-if="normalizedSlides.length > 1" class="dots">
      <button
        v-for="(_, i) in normalizedSlides"
        :key="i"
        type="button"
        :class="{ on: i === index }"
        @click="index = i"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  slides: { type: Array, default: () => [] },
  intervalMs: { type: Number, default: 3500 },
})

const index = ref(0)
let timer
const apiBaseUrl = String(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const normalizedSlides = computed(() =>
  (props.slides || []).map((slide) => ({
    ...slide,
    imageUrl:
      slide?.imageUrl && /^https?:\/\//i.test(slide.imageUrl)
        ? slide.imageUrl
        : `${apiBaseUrl}${slide?.imageUrl || ''}`,
  })),
)

watch(
  () => props.slides,
  () => {
    index.value = 0
  },
)

function tick() {
  const n = normalizedSlides.value?.length || 0
  if (n <= 1) return
  index.value = (index.value + 1) % n
}

onMounted(() => {
  timer = setInterval(tick, props.intervalMs)
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.carousel {
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: center;
}
.track {
  display: flex;
  width: 100%;
  transition: transform 0.5s ease;
}
.slide {
  flex: 0 0 100%;
  display: flex;
  justify-content: center;
}
.slide-image {
  display: block;
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: 70vh;
  object-fit: contain;
  margin: 0 auto;
}
.empty {
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 14px;
}
.dots {
  position: absolute;
  bottom: 10px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: center;
  gap: 6px;
}
.dots button {
  width: 8px;
  height: 8px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  cursor: pointer;
}
.dots button.on {
  background: #fff;
}
</style>
