<template>
  <div style="display: flex; height: 100vh;">
    <div style="width: 20%; border-right: 1px solid #ddd; padding: 10px;">
      <h3>当前小说</h3>
      <el-button @click="$router.back()">返回</el-button>
    </div>
    <div style="width: 60%; display: flex; flex-direction: column;">
      <div ref="messagesContainer" style="flex: 1; overflow-y: auto; padding: 20px;">
        <div v-for="(msg, idx) in messages" :key="idx" style="margin-bottom: 15px;">
          <div v-if="msg.role === 'user'" style="text-align: right;">
            <span style="display: inline-block; padding: 10px 15px; border-radius: 8px; background-color: #409EFF; color: white; max-width: 70%; text-align: left;">
              {{ msg.content }}
            </span>
          </div>
          <div v-else style="text-align: left;">
            <span style="display: inline-block; padding: 10px 15px; border-radius: 8px; background-color: #f0f0f0; color: black; max-width: 70%; text-align: left;">
              {{ msg.content }}
            </span>
          </div>
        </div>
      </div>
      <div style="padding: 20px; border-top: 1px solid #ddd;">
        <el-input v-model="input" @keyup.enter="sendMessage" placeholder="输入消息..." />
        <el-button type="primary" @click="sendMessage" style="margin-top: 10px;">发送</el-button>
      </div>
    </div>
    <div style="width: 20%; border-left: 1px solid #ddd; padding: 10px;">
      <h3>章节预览</h3>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'

const route = useRoute()
const userStore = useUserStore()
const messages = ref([])
const input = ref('')
let ws = null

onMounted(() => {
  const novelId = route.params.id
  const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
  ws = new WebSocket(`${wsUrl}/ws/chat/${novelId}?token=${userStore.token}`)

  ws.onopen = () => {
    console.log('WebSocket connected')
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'message_sent') {
      messages.value.push({ role: 'assistant', content: data.content })
    }
  }
})

function sendMessage() {
  if (!input.value.trim()) return
  console.log('发送消息:', input.value)
  console.log('WebSocket状态:', ws?.readyState)
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.error('WebSocket未连接')
    return
  }
  messages.value.push({ role: 'user', content: input.value })
  ws.send(JSON.stringify({ type: 'message', content: input.value }))
  input.value = ''
}
</script>
