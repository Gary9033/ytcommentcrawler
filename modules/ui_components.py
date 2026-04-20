"""
UI Components Module
Reusable Streamlit components for European Minimal Design
"""

import streamlit as st
from typing import Optional, Callable, Any


def load_css() -> None:
    """加載歐洲極簡CSS樣式"""
    try:
        with open("styles/european_minimal.css", "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("⚠️ CSS 文件未找到，使用默認主題")


def header_section(
    title: str,
    subtitle: Optional[str] = None,
    icon: str = "🎬",
    centered: bool = True
) -> None:
    """
    渲染標題部分
    
    Args:
        title: 主標題文本
        subtitle: 副標題文本（可選）
        icon: 標題前的 emoji 圖標
        centered: 是否居中
    """
    col1, col2, col3 = st.columns([1, 2, 1]) if centered else (None, None, None)
    
    target_col = col2 if centered else st
    
    with target_col:
        st.markdown(f"# {icon} {title}")
        if subtitle:
            st.markdown(f"*{subtitle}*", help=None)


def input_card(
    label: str,
    key: str,
    placeholder: str = "",
    disabled: bool = False,
    help_text: Optional[str] = None,
    input_type: str = "text"
) -> str:
    """
    渲染輸入卡片
    
    Args:
        label: 輸入框標籤
        key: Streamlit session state key
        placeholder: 佔位符文本
        disabled: 是否禁用
        help_text: 幫助文本
        input_type: 輸入類型（'text', 'password', 等）
    
    Returns:
        用戶輸入值
    """
    return st.text_input(
        label=label,
        key=key,
        placeholder=placeholder,
        disabled=disabled,
        help=help_text
    )


def action_button(
    label: str,
    key: str,
    on_click: Optional[Callable] = None,
    disabled: bool = False,
    help_text: Optional[str] = None,
    button_type: str = "primary"
) -> bool:
    """
    渲染操作按鈕
    
    Args:
        label: 按鈕文本
        key: Streamlit session state key
        on_click: 點擊回調函數
        disabled: 是否禁用
        help_text: 幫助文本
        button_type: 按鈕類型 ('primary', 'secondary')
    
    Returns:
        按鈕是否被點擊
    """
    return st.button(
        label=label,
        key=key,
        on_click=on_click,
        disabled=disabled,
        help=help_text,
        use_container_width=True
    )


def progress_indicator(
    value: float,
    label: str = "進度",
    max_value: float = 100.0
) -> None:
    """
    渲染進度指示器
    
    Args:
        value: 當前進度值
        label: 進度標籤
        max_value: 最大值
    """
    progress = min(value / max_value, 1.0)
    st.progress(progress, text=f"{label}: {int(progress * 100)}%")


def info_box(
    content: str,
    box_type: str = "info"
) -> None:
    """
    渲染信息框
    
    Args:
        content: 框內容
        box_type: 框類型 ('info', 'success', 'warning', 'error')
    """
    if box_type == "success":
        st.success(content)
    elif box_type == "warning":
        st.warning(content)
    elif box_type == "error":
        st.error(content)
    else:
        st.info(content)


def two_column_layout(
    left_content: Callable,
    right_content: Callable,
    ratio: tuple = (1, 1)
) -> None:
    """
    渲染兩列佈局
    
    Args:
        left_content: 左列內容回調
        right_content: 右列內容回調
        ratio: 列寬比 (left, right)
    """
    left_col, right_col = st.columns(ratio)
    
    with left_col:
        left_content()
    
    with right_col:
        right_content()


def data_display_table(
    df,
    title: str = "",
    sortable: bool = True,
    show_index: bool = False
) -> None:
    """
    渲染數據顯示表格
    
    Args:
        df: pandas DataFrame
        title: 表格標題
        sortable: 是否可排序
        show_index: 是否顯示索引
    """
    if title:
        st.subheader(title)
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=show_index,
        height=400
    )


def section_divider(height: int = 20) -> None:
    """
    渲染幾何分隔符
    
    Args:
        height: 分隔符高度（像素）
    """
    st.markdown(f"<div style='height: {height}px'></div>", unsafe_allow_html=True)


def geometric_divider() -> None:
    """渲染幾何風格分隔線"""
    st.markdown(
        '<div style="width:40px;height:2px;background-color:#3B82F6;margin:24px auto;"></div>',
        unsafe_allow_html=True
    )


def labeled_metric(
    label: str,
    value: str,
    delta: Optional[str] = None,
    icon: str = "📊"
) -> None:
    """
    渲染帶標籤的指標
    
    Args:
        label: 標籤
        value: 指標值
        delta: 變化值
        icon: 指標圖標
    """
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(f"## {icon}")
    with col2:
        st.markdown(f"**{label}**")
        st.markdown(f"# {value}")
        if delta:
            st.markdown(f"*{delta}*")


def download_button_custom(
    label: str,
    data: bytes,
    file_name: str,
    mime: str = "text/plain",
    key: str = None
) -> bool:
    """
    渲染自定義下載按鈕
    
    Args:
        label: 按鈕標籤
        data: 下載數據
        file_name: 文件名
        mime: MIME 類型
        key: Streamlit key
    
    Returns:
        按鈕是否被點擊
    """
    return st.download_button(
        label=label,
        data=data,
        file_name=file_name,
        mime=mime,
        key=key,
        use_container_width=True
    )
