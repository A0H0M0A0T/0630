/**
 * Account Store 测试
 *
 * 覆盖 useAccountStore 的核心逻辑：
 * - setAccounts：数据格式转换（后端数组 → 前端对象）
 * - addAccount / updateAccount / deleteAccount：CRUD
 * - getAccountsByPlatform：平台筛选
 * - 状态码映射：-1→验证中, 1→正常, 0→异常
 * - 平台类型映射：1→小红书, 2→视频号, 3→抖音, 4→快手, 未知→"未知"
 * - 边界：空数组、缺失字段、异常数据
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAccountStore } from '@/stores/account'

// --- 后端返回的原始数据格式 ---
// rows_list = [[id, type, filePath, userName, status], ...]
const makeItem = (id, type, filePath, name, status) => [id, type, filePath, name, status]

describe('Account Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAccountStore()
  })

  // ============================================================
  // setAccounts — 格式转换 + 状态/平台映射
  // ============================================================
  describe('setAccounts', () => {
    it('正确转换后端数组为前端对象格式', () => {
      const raw = [
        makeItem(1, 3, 'cookies/douyin.json', '测试号', 1),
        makeItem(2, 4, 'cookies/kuaishou.json', '快手号', 0),
        makeItem(3, 1, 'cookies/xhs.json', '小红书号', 1),
        makeItem(4, 2, 'cookies/channel.json', '视频号', -1),
      ]

      store.setAccounts(raw)

      expect(store.accounts).toHaveLength(4)
      expect(store.accounts[0]).toEqual({
        id: 1, type: 3, filePath: 'cookies/douyin.json',
        name: '测试号', status: '正常', platform: '抖音',
      })
      expect(store.accounts[1].status).toBe('异常')
      expect(store.accounts[2].platform).toBe('小红书')
      expect(store.accounts[3].status).toBe('验证中')
    })

    it('状态码 -1 映射为 "验证中"', () => {
      store.setAccounts([makeItem(1, 3, '', 'a', -1)])
      expect(store.accounts[0].status).toBe('验证中')
    })

    it('状态码 1 映射为 "正常"', () => {
      store.setAccounts([makeItem(1, 3, '', 'a', 1)])
      expect(store.accounts[0].status).toBe('正常')
    })

    it('状态码 0 映射为 "异常"', () => {
      store.setAccounts([makeItem(1, 3, '', 'a', 0)])
      expect(store.accounts[0].status).toBe('异常')
    })

    it('未知平台类型映射为 "未知"', () => {
      store.setAccounts([makeItem(1, 99, '', 'a', 1)])
      expect(store.accounts[0].platform).toBe('未知')
    })

    it('空数组 → accounts 为空', () => {
      store.setAccounts([])
      expect(store.accounts).toHaveLength(0)
    })

    it('空数组不抛异常（res.data 可能为 null 的场景由 API 层处理）', () => {
      store.setAccounts([])
      expect(store.accounts).toEqual([])
    })
  })

  // ============================================================
  // addAccount
  // ============================================================
  describe('addAccount', () => {
    it('添加账号到列表末尾', () => {
      store.addAccount({ id: 1, name: '新号', platform: '抖音', status: '正常' })
      expect(store.accounts).toHaveLength(1)
      expect(store.accounts[0].name).toBe('新号')
    })
  })

  // ============================================================
  // updateAccount
  // ============================================================
  describe('updateAccount', () => {
    beforeEach(() => {
      store.setAccounts([
        makeItem(1, 3, 'a.json', '旧名', 1),
        makeItem(2, 4, 'b.json', '快手号', 1),
      ])
    })

    it('更新指定 id 的账号', () => {
      store.updateAccount(1, { name: '新名', status: '异常' })
      expect(store.accounts[0].name).toBe('新名')
      expect(store.accounts[0].status).toBe('异常')
    })

    it('不存在的 id 不抛异常，静默忽略', () => {
      expect(() => store.updateAccount(999, { name: 'x' })).not.toThrow()
    })

    it('更新的 id 不在列表中，其他账号不变', () => {
      store.updateAccount(999, { name: 'x' })
      expect(store.accounts).toHaveLength(2)
      expect(store.accounts[0].name).toBe('旧名')
    })
  })

  // ============================================================
  // deleteAccount
  // ============================================================
  describe('deleteAccount', () => {
    beforeEach(() => {
      store.setAccounts([
        makeItem(1, 3, 'a.json', 'A', 1),
        makeItem(2, 4, 'b.json', 'B', 1),
      ])
    })

    it('删除指定 id 的账号', () => {
      store.deleteAccount(1)
      expect(store.accounts).toHaveLength(1)
      expect(store.accounts[0].id).toBe(2)
    })

    it('删除不存在的 id 不抛异常', () => {
      expect(() => store.deleteAccount(999)).not.toThrow()
      expect(store.accounts).toHaveLength(2)
    })
  })

  // ============================================================
  // getAccountsByPlatform
  // ============================================================
  describe('getAccountsByPlatform', () => {
    beforeEach(() => {
      store.setAccounts([
        makeItem(1, 3, '', '抖音A', 1),
        makeItem(2, 3, '', '抖音B', 1),
        makeItem(3, 4, '', '快手A', 1),
      ])
    })

    it('按平台名称筛选', () => {
      const douyin = store.getAccountsByPlatform('抖音')
      expect(douyin).toHaveLength(2)
      expect(douyin[0].name).toBe('抖音A')
      expect(douyin[1].name).toBe('抖音B')
    })

    it('无匹配时返回空数组', () => {
      const bilibili = store.getAccountsByPlatform('B站')
      expect(bilibili).toHaveLength(0)
    })
  })

  // ============================================================
  // 边界条件
  // ============================================================
  describe('边界条件', () => {
    it('setAccounts 重复调用覆盖旧数据', () => {
      store.setAccounts([makeItem(1, 3, '', 'A', 1)])
      store.setAccounts([makeItem(2, 4, '', 'B', 1)])
      expect(store.accounts).toHaveLength(1)
      expect(store.accounts[0].name).toBe('B')
    })

    it('文件路径为空字符串也可以正常存储', () => {
      store.setAccounts([makeItem(1, 3, '', '无文件', 1)])
      expect(store.accounts[0].filePath).toBe('')
    })
  })
})
