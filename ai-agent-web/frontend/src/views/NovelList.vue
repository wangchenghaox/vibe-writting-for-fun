<template>
  <div style="padding: 20px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
      <h2>我的小说</h2>
      <el-button type="primary" @click="$router.push('/login'); userStore.logout()">退出</el-button>
    </div>
    <el-row :gutter="20">
      <el-col :span="6" v-for="novel in novels" :key="novel.id">
        <el-card @click="$router.push(`/novels/${novel.id}`)" style="cursor: pointer;">
          <h3>{{ novel.title }}</h3>
          <p>{{ novel.description }}</p>
          <p>章节数: {{ novel.chapter_count }} | 总字数: {{ novel.total_words }}</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '../stores/user'
import api from '../api/client'

const novels = ref([])
const userStore = useUserStore()

onMounted(async () => {
  const { data } = await api.get('/api/novels')
  novels.value = data
})
</script>
