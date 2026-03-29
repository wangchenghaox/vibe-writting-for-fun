<template>
  <div style="padding: 20px;">
    <el-button @click="$router.push('/novels')">返回</el-button>
    <h2>{{ novel?.title }}</h2>
    <p>{{ novel?.description }}</p>
    <el-button type="primary" @click="$router.push(`/novels/${$route.params.id}/chat`)">开始对话</el-button>
    <h3>章节列表</h3>
    <el-collapse v-if="novel?.chapters">
      <el-collapse-item v-for="chapter in novel.chapters" :key="chapter.id" :title="`${chapter.title} (${chapter.word_count}字)`">
        <p>{{ chapter.content }}</p>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'

const route = useRoute()
const novel = ref(null)

onMounted(async () => {
  const { data } = await api.get(`/api/novels/${route.params.id}`)
  novel.value = data
})
</script>
