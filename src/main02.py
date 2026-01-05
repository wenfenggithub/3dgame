from direct.showbase.ShowBase import ShowBase
from panda3d.core import WindowProperties, Vec3, CollisionTraverser, CollisionNode, CollisionSphere, CollisionHandlerEvent, TextNode
from direct.task import Task
from direct.gui.OnscreenText import OnscreenText
import random
import sys

class PlayerController:
    """
    玩家控制器：处理玩家输入（WASD），并移动玩家节点
    """
    def __init__(self, player_node, speed=10):
        self.player_node = player_node  # 玩家模型节点
        self.speed = speed              # 玩家移动速度
        # 输入状态字典，记录每个方向键是否被按下
        self.input_state = {"forward": False, "backward": False, "left": False, "right": False}
        self.accept_input()             # 注册输入事件

    def accept_input(self):
        """
        注册WASD键盘事件，按下和松开分别设置input_state
        """
        base.accept("w", self.set_key, ["forward", True])
        base.accept("w-up", self.set_key, ["forward", False])
        base.accept("s", self.set_key, ["backward", True])
        base.accept("s-up", self.set_key, ["backward", False])
        base.accept("a", self.set_key, ["left", True])
        base.accept("a-up", self.set_key, ["left", False])
        base.accept("d", self.set_key, ["right", True])
        base.accept("d-up", self.set_key, ["right", False])

    def set_key(self, key, value):
        """
        设置某个方向的输入状态
        """
        self.input_state[key] = value

    def update(self, dt):
        """
        每帧调用，根据input_state移动玩家
        dt: delta time, 帧间隔秒数
        """
        direction = Vec3(0, 0, 0)
        # 根据输入方向累加方向向量
        if self.input_state["forward"]:
            direction.y += 1
        if self.input_state["backward"]:
            direction.y -= 1
        if self.input_state["left"]:
            direction.x -= 1
        if self.input_state["right"]:
            direction.x += 1
        # 如果有输入，归一化方向并移动玩家
        if direction.length_squared() > 0:
            direction.normalize()
            move_vec = direction * self.speed * dt
            self.player_node.set_pos(self.player_node.get_pos() + move_vec)

class ThirdPersonCamera:
    """
    第三人称相机控制器：让相机跟随玩家，并保持一定距离和高度
    """
    def __init__(self, target_node, distance=10, height=3):
        self.target_node = target_node  # 跟随目标（玩家模型）
        self.distance = distance        # 相机与玩家的后方距离
        self.height = height            # 相机高度

    def update(self):
        """
        每帧调用，更新相机位置和朝向
        """
        player_pos = self.target_node.get_pos()
        # 计算相机在玩家后方和上方的位置（假设玩家面向+Y轴）
        cam_offset = Vec3(0, -self.distance, self.height)
        cam_pos = player_pos + cam_offset
        base.camera.set_pos(cam_pos)
        # 让相机看向玩家头部（略高于模型中心）
        base.camera.look_at(player_pos + Vec3(0, 0, 1.5))

class Bullet:
    """
    子弹类：负责子弹的生成、移动和销毁
    """
    def __init__(self, pos, direction, bullet_root, traverser, handler):
        # 用球体表示子弹
        self.model = loader.loadModel("models/ball")
        self.model.setScale(0.2)
        self.model.setColor(1, 1, 0, 1)
        self.model.setPos(pos)
        self.model.reparentTo(bullet_root)
        self.speed = 30
        self.direction = direction.normalized()

        # 碰撞体
        self.cnode = CollisionNode('bullet')
        self.cnode.addSolid(CollisionSphere(0, 0, 0, 0.2))
        self.cnode.setFromCollideMask(0x1)
        self.cnode.setIntoCollideMask(0)
        self.cnodepath = self.model.attachNewNode(self.cnode)
        traverser.addCollider(self.cnodepath, handler)
        self.cnodepath.setPythonTag("owner", self)

        self.alive = True

    def update(self, dt):
        if not self.alive:
            return
        move_vec = self.direction * self.speed * dt
        self.model.setPos(self.model.getPos() + move_vec)
        # 超出范围自动销毁
        if self.model.getY() > 100 or self.model.getY() < -100 or abs(self.model.getX()) > 100:
            self.destroy()

    def destroy(self):
        self.alive = False
        self.model.removeNode()

class Target:
    """
    目标类：被击中后重生
    """
    def __init__(self, pos, root, traverser, handler):
        self.model = loader.loadModel("models/box")
        self.model.setScale(0.5)
        self.model.setColor(1, 0, 0, 1)
        self.model.setPos(pos)
        self.model.reparentTo(root)

        self.cnode = CollisionNode('target')
        self.cnode.addSolid(CollisionSphere(0, 0, 0, 0.5))
        self.cnode.setFromCollideMask(0)
        self.cnode.setIntoCollideMask(0x1)
        self.cnodepath = self.model.attachNewNode(self.cnode)
        self.cnodepath.setPythonTag("owner", self)

    def respawn(self):
        # 随机新位置
        x = random.uniform(-8, 8)
        y = random.uniform(10, 30)
        self.model.setPos(x, y, 0)

    def destroy(self):
        self.model.removeNode()

class MyApp(ShowBase):
    """
    主应用类，负责初始化窗口、加载模型、设置控制器和主循环
    """
    def __init__(self):
        ShowBase.__init__(self)
        self.disableMouse()  # 禁用Panda3D默认鼠标相机控制

        # 设置窗口标题
        props = WindowProperties()
        props.setTitle("Panda3D 简单射击游戏")
        self.win.requestProperties(props)

        # 分数
        self.score = 0
        self.score_text = OnscreenText(text="分数: 0", pos=(-1.2, 0.9), scale=0.07, fg=(1,1,1,1), align=TextNode.ALeft, mayChange=True)

        # 加载玩家模型（使用内置panda模型做演示）
        self.player = loader.loadModel("models/panda")
        self.player.setScale(0.005)        # 缩小模型
        self.player.reparentTo(render)     # 挂到场景根节点
        self.player.setPos(0, 0, 0)        # 初始位置

        # 创建玩家控制器
        self.player_controller = PlayerController(self.player, speed=10)

        # 创建第三人称相机控制器
        self.camera_controller = ThirdPersonCamera(self.player, distance=15, height=5)

        # 添加主循环任务，每帧调用self.update
        self.taskMgr.add(self.update, "update")

        # 创建简单环境
        self.setup_environment()

        # 子弹和目标管理
        self.bullets = []
        self.targets = []

        # 碰撞系统
        self.cTrav = CollisionTraverser()
        self.collHandEvent = CollisionHandlerEvent()
        self.collHandEvent.addInPattern('%fn-into-%in')

        # 创建目标
        self.target_root = render.attachNewNode("targets")
        for _ in range(3):
            t = Target(self.random_target_pos(), self.target_root, self.cTrav, self.collHandEvent)
            self.targets.append(t)

        # 子弹父节点
        self.bullet_root = render.attachNewNode("bullets")

        # 注册碰撞事件
        self.accept("bullet-into-target", self.on_bullet_hit_target)

        # 按空格发射子弹
        self.accept("space", self.shoot_bullet)

        # 按ESC退出程序
        self.accept("escape", sys.exit)

    def setup_environment(self):
        """
        加载地面环境模型
        """
        ground = loader.loadModel("models/environment")
        ground.reparentTo(render)
        ground.setScale(0.1)
        ground.setPos(-8, 42, 0)

    def random_target_pos(self):
        x = random.uniform(-8, 8)
        y = random.uniform(10, 30)
        return Vec3(x, y, 0)

    def shoot_bullet(self):
        # 子弹从玩家头部发射，方向为+Y
        pos = self.player.getPos() + Vec3(0, 0, 1.5)
        direction = Vec3(0, 1, 0)
        bullet = Bullet(pos, direction, self.bullet_root, self.cTrav, self.collHandEvent)
        self.bullets.append(bullet)

    def on_bullet_hit_target(self, entry):
        bullet_node = entry.getFromNodePath().getPythonTag("owner")
        target_node = entry.getIntoNodePath().getPythonTag("owner")
        # 销毁子弹
        if bullet_node and bullet_node.alive:
            bullet_node.destroy()
        # 目标重生
        if target_node:
            target_node.respawn()
        # 分数+1
        self.score += 1
        self.score_text.setText(f"分数: {self.score}")

    def update(self, task):
        """
        主循环任务，每帧调用
        """
        dt = globalClock.getDt()  # 获取帧间隔秒数
        self.player_controller.update(dt)
        self.camera_controller.update()

        # 更新子弹
        for bullet in self.bullets[:]:
            if bullet.alive:
                bullet.update(dt)
            else:
                self.bullets.remove(bullet)

        # 碰撞检测
        self.cTrav.traverse(render)

        return Task.cont  # 继续下一帧

if __name__ == "__main__":
    app = MyApp()
    app.run()