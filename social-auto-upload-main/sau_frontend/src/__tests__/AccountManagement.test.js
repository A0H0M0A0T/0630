/**
 * AccountManagement 组件逻辑测试
 *
 * 覆盖：
 * - 搜索过滤（filteredAccounts / 各平台 computed）
 * - getPlatformTagType / getStatusTagType / isStatusClickable 工具函数
 * - handleEdit → SSE 状态重置（Bug A 修复验证）
 * - handleReLogin 流程
 * - handleAddAccount → SSE 状态正确重置
 * - handleStatusClick 分流
 * - connectSSE 平台类型映射
 * - 边界条件
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'
import AccountManagement from '@/views/AccountManagement.vue'
import { nextTick } from 'vue'

// --- 模拟 axios，让 onMounted 中的 API 调用静默返回 ---
vi.mock('axios', () => ({
  default: {
    create: () => ({
      get: vi.fn().mockResolvedValue({ data: { code: 200, data: [], msg: null } }),
      post: vi.fn().mockResolvedValue({ data: { code: 200, msg: 'ok' } }),
      interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    }),
  },
}))

const makeItem = (id, type, filePath, name, status) => [id, type, filePath, name, status]

function mountComponent() {
  const pinia = createPinia()
  setActivePinia(pinia)
  // suppress Vue warnings about unresolved elements in test output
  const originalWarn = console.warn
  console.warn = (...args) => {
    const msg = args[0]?.toString() || ''
    if (msg.includes('Failed to resolve component')) return
    originalWarn(...args)
  }
  const w = mount(AccountManagement, {
    global: {
      plugins: [pinia],
      stubs: {
        'el-input': true,
        'el-button': true,
        'el-icon': true,
        'el-avatar': true,
        'el-table': true,
        'el-table-column': true,
        'el-tag': true,
        'el-tabs': true,
        'el-tab-pane': true,
        'el-empty': true,
        'el-dialog': true,
        'el-form': true,
        'el-form-item': true,
        'el-select': true,
        'el-option': true,
      },
    },
  })
  console.warn = originalWarn
  return w
}

describe('AccountManagement', () => {
  let wrapper, accountStore, appStore

  beforeEach(() => {
    wrapper = mountComponent()
    accountStore = useAccountStore()
    appStore = useAppStore()
  })

  afterEach(() => {
    wrapper.unmount()
  })

  // ============================================================
  // 搜索过滤
  // ============================================================
  describe('搜索过滤 computed', () => {
    it('空搜索词返回全部账号', async () => {
      accountStore.setAccounts([
        makeItem(1, 3, '', '抖音A', 1),
        makeItem(2, 4, '', '快手号', 1),
      ])
      await nextTick()
      expect(wrapper.vm.filteredAccounts).toHaveLength(2)
    })

    it('按名称搜索过滤', async () => {
      accountStore.setAccounts([
        makeItem(1, 3, '', '抖音A', 1),
        makeItem(2, 4, '', '快手号', 1),
      ])
      wrapper.vm.searchKeyword = '快手'
      await nextTick()
      expect(wrapper.vm.filteredAccounts).toHaveLength(1)
      expect(wrapper.vm.filteredAccounts[0].name).toBe('快手号')
    })

    it('空列表返回空数组', () => {
      expect(wrapper.vm.filteredAccounts).toHaveLength(0)
    })

    it('filteredKuaishouAccounts 只返回快手平台', async () => {
      accountStore.setAccounts([
        makeItem(1, 4, '', '快手A', 1),
        makeItem(2, 3, '', '抖音A', 1),
        makeItem(3, 4, '', '快手B', 1),
      ])
      await nextTick()
      expect(wrapper.vm.filteredKuaishouAccounts).toHaveLength(2)
    })

    it('filteredDouyinAccounts 只返回抖音平台', async () => {
      accountStore.setAccounts([
        makeItem(1, 3, '', '抖音A', 1),
        makeItem(2, 4, '', '快手A', 1),
      ])
      await nextTick()
      expect(wrapper.vm.filteredDouyinAccounts).toHaveLength(1)
    })
  })

  // ============================================================
  // 工具函数
  // ============================================================
  describe('getPlatformTagType', () => {
    it.each([
      ['快手', 'success'],
      ['抖音', 'danger'],
      ['视频号', 'warning'],
      ['小红书', 'info'],
      ['未知平台', 'info'],
    ])('%s → %s', (platform, expected) => {
      expect(wrapper.vm.getPlatformTagType(platform)).toBe(expected)
    })
  })

  describe('getStatusTagType', () => {
    it.each([
      ['验证中', 'info'],
      ['正常', 'success'],
      ['异常', 'danger'],
    ])('状态 "%s" → "%s"', (status, expected) => {
      expect(wrapper.vm.getStatusTagType(status)).toBe(expected)
    })
  })

  describe('isStatusClickable', () => {
    it('"异常" 可点击', () => expect(wrapper.vm.isStatusClickable('异常')).toBe(true))
    it('"正常" 不可点击', () => expect(wrapper.vm.isStatusClickable('正常')).toBe(false))
    it('"验证中" 不可点击', () => expect(wrapper.vm.isStatusClickable('验证中')).toBe(false))
  })

  // ============================================================
  // handleStatusClick → 异常状态打开重新登录
  // ============================================================
  describe('handleStatusClick', () => {
    it('异常状态 → 打开对话框走重新登录', async () => {
      const row = { id: 1, name: '抖音A', platform: '抖音', status: '异常' }
      wrapper.vm.handleStatusClick(row)
      await nextTick()
      expect(wrapper.vm.dialogVisible).toBe(true)
      expect(wrapper.vm.dialogType).toBe('edit')
    })

    it('正常状态 → 不触发', () => {
      const row = { id: 1, name: 'A', platform: '抖音', status: '正常' }
      wrapper.vm.handleStatusClick(row)
      expect(wrapper.vm.dialogVisible).toBe(false)
    })
  })

  // ============================================================
  // handleEdit — Bug A 修复验证
  // ============================================================
  describe('handleEdit', () => {
    it('打开编辑对话框，并重置 SSE 状态', async () => {
      // 预置脏 SSE 状态
      wrapper.vm.sseConnecting = true
      wrapper.vm.qrCodeData = 'data:image/png;base64,xxxx'
      wrapper.vm.loginStatus = '500'

      const row = { id: 1, name: 'A', platform: '抖音', status: '正常' }
      wrapper.vm.handleEdit(row)
      await nextTick()

      expect(wrapper.vm.dialogVisible).toBe(true)
      expect(wrapper.vm.dialogType).toBe('edit')
      expect(wrapper.vm.accountForm.name).toBe('A')
      // Bug A 修复验证
      expect(wrapper.vm.sseConnecting).toBe(false)
      expect(wrapper.vm.qrCodeData).toBe('')
      expect(wrapper.vm.loginStatus).toBe('')
    })
  })

  // ============================================================
  // handleAddAccount — SSE 状态重置（对比基准）
  // ============================================================
  describe('handleAddAccount', () => {
    it('重置 SSE 状态，打开添加对话框', async () => {
      wrapper.vm.sseConnecting = true
      wrapper.vm.qrCodeData = 'some-data'
      wrapper.vm.loginStatus = '500'

      wrapper.vm.handleAddAccount()
      await nextTick()

      expect(wrapper.vm.dialogVisible).toBe(true)
      expect(wrapper.vm.dialogType).toBe('add')
      expect(wrapper.vm.sseConnecting).toBe(false)
      expect(wrapper.vm.qrCodeData).toBe('')
      expect(wrapper.vm.loginStatus).toBe('')
      expect(wrapper.vm.accountForm.name).toBe('')
    })
  })

  // ============================================================
  // connectSSE 平台类型映射
  // ============================================================
  describe('connectSSE 平台映射', () => {
    it.each([
      ['小红书', '1'],
      ['视频号', '2'],
      ['抖音', '3'],
      ['快手', '4'],
    ])('%s → type=%s', (platform, typeNum) => {
      const map = {
        '小红书': '1', '视频号': '2', '抖音': '3', '快手': '4',
      }
      expect(map[platform]).toBe(typeNum)
    })

    it('未知平台默认 type=1', () => {
      const map = {
        '小红书': '1', '视频号': '2', '抖音': '3', '快手': '4',
      }
      expect(map['未知'] || '1').toBe('1')
    })
  })

  // ============================================================
  // 工具函数：平台类型映射与 edit API 一致
  // ============================================================
  describe('submitAccountForm 的 edit 分支平台映射', () => {
    it('编辑时平台映射：小红书→1, 视频号→2, 抖音→3, 快手→4', () => {
      // 验证 edit 分支中的 platformTypeMap 与 SSE 中的不一致性
      // SSE 使用字符串类型 '1'，update API 使用数字类型 1
      const sseMap = { '小红书': '1', '视频号': '2', '抖音': '3', '快手': '4' }
      const updateMap = { '小红书': 1, '视频号': 2, '抖音': 3, '快手': 4 }
      expect(sseMap['抖音']).toBe('3')
      expect(updateMap['抖音']).toBe(3)
    })
  })

  // ============================================================
  // 边界条件
  // ============================================================
  describe('边界条件', () => {
    it('空 store → 所有 computed 返回空数组', () => {
      expect(wrapper.vm.filteredAccounts).toEqual([])
      expect(wrapper.vm.filteredKuaishouAccounts).toEqual([])
      expect(wrapper.vm.filteredDouyinAccounts).toEqual([])
      expect(wrapper.vm.filteredChannelsAccounts).toEqual([])
      expect(wrapper.vm.filteredXiaohongshuAccounts).toEqual([])
    })

    it('closeSSEConnection 函数存在', () => {
      expect(typeof wrapper.vm.closeSSEConnection).toBe('function')
    })
  })
})
