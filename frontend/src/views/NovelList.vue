<template>
  <div style="padding: 20px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
      <h2>我的小说</h2>
      <div>
        <el-button type="primary" @click="createNovel">创建小说</el-button>
        <el-button @click="$router.push('/login'); userStore.logout()">退出</el-button>
      </div>
    </div>
    <div v-if="novels.length === 0" style="text-align: center; padding: 40px; color: #999;">
      暂无小说，请先创建小说
    </div>
    <el-row :gutter="20" v-else>
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
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'
import api from '../api/client'

const novels = ref([])
const userStore = useUserStore()
const router = useRouter()

onMounted(async () => {
  loadNovels()
})

async function loadNovels() {
  const { data } = await api.get('/api/novels')
  novels.value = data
}

async function createNovel() {
  try {
    const novel_id = 'novel_' + Date.now()
    const { data } = await api.post('/api/novels', {
      novel_id,
      title: '新小说',
      description: '通过对话生成'
    })
    router.push(`/novels/${data.id}/chat`)
  } catch (error) {
    console.error('创建小说失败:', error.response?.data || error.message)
    ElMessage.error('创建失败: ' + (error.response?.data?.detail || error.message))
  }
}
</script>
