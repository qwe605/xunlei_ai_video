interface VideoThumbnailProps {
  cell: number
  alt: string
  className?: string
  imageUrl?: string
}

const positions = [
  '0% 0%',
  '33.333% 0%',
  '66.667% 0%',
  '100% 0%',
  '0% 50%',
  '33.333% 50%',
  '66.667% 50%',
  '100% 50%',
  '0% 100%',
  '33.333% 100%',
  '66.667% 100%',
  '100% 100%',
]

export function VideoThumbnail({ cell, alt, className = '', imageUrl }: VideoThumbnailProps) {
  return (
    <div
      className={`video-thumbnail ${className}`}
      role="img"
      aria-label={alt}
      style={{
        backgroundImage: imageUrl ? `url("${imageUrl}")` : undefined,
        backgroundPosition: imageUrl ? 'center' : (positions[cell] ?? positions[0]),
        backgroundSize: imageUrl ? 'cover' : '400% 300%',
      }}
    />
  )
}
