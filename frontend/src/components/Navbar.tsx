import React from 'react'
import { Typography, Space, Button, Tag, Tooltip } from 'antd'
import {
  BookOutlined,
  BulbOutlined,
  BulbFilled,
  MenuOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'

const { Text } = Typography

interface NavbarProps {
  currentDocumentTitle?: string
  isDarkMode: boolean
  onToggleDarkMode: () => void
  onToggleSidebar?: () => void
  isMobile?: boolean
}

export const Navbar: React.FC<NavbarProps> = ({
  currentDocumentTitle,
  isDarkMode,
  onToggleDarkMode,
  onToggleSidebar,
  isMobile,
}) => {
  return (
    <header
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0 20px',
        height: 56,
        background: isDarkMode ? '#141414' : '#ffffff',
        borderBottom: isDarkMode ? '1px solid #303030' : '1px solid #f0f0f0',
        zIndex: 10,
      }}
    >
      <Space size={12}>
        {isMobile && (
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={onToggleSidebar}
            style={{ marginRight: 4 }}
          />
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #1677ff 0%, #722ed1 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontSize: 18,
            }}
          >
            <BookOutlined />
          </div>
          <div>
            <span
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: isDarkMode ? '#fff' : '#1f1f1f',
                letterSpacing: '-0.3px',
              }}
            >
              AI PDF Reader
            </span>
          </div>
        </div>

        {currentDocumentTitle && (
          <div
            style={{
              marginLeft: 16,
              paddingLeft: 16,
              borderLeft: isDarkMode ? '1px solid #303030' : '1px solid #e8e8e8',
              maxWidth: 360,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            <Text
              style={{
                fontSize: 13,
                color: isDarkMode ? '#aaa' : '#666',
              }}
            >
              Đang đọc:{' '}
              <strong style={{ color: isDarkMode ? '#fff' : '#1f1f1f' }}>
                {currentDocumentTitle}
              </strong>
            </Text>
          </div>
        )}
      </Space>

      <Space size={12}>
        <Tooltip title="Chống ảo giác (Anti-Hallucination) kích hoạt">
          <Tag
            color="success"
            icon={<SafetyCertificateOutlined />}
            style={{ borderRadius: 12, padding: '2px 10px', fontSize: 12 }}
          >
            Grounding Active
          </Tag>
        </Tooltip>

        <Tooltip title={isDarkMode ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối'}>
          <Button
            type="text"
            shape="circle"
            icon={isDarkMode ? <BulbFilled style={{ color: '#faad14' }} /> : <BulbOutlined />}
            onClick={onToggleDarkMode}
          />
        </Tooltip>
      </Space>
    </header>
  )
}
